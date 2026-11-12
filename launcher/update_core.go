package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

// Phần lõi cập nhật: không phụ thuộc mạng/dịch vụ để kiểm thử được.
//
// Quy ước gói phát hành (zip): chứa mã nguồn + vendor + public/build, file VERSION, và
// release-manifest.txt liệt kê (mỗi dòng một đường dẫn tương đối, dấu /) mọi file trong gói.
// Chỉ file có trong manifest mới được giải nén; file có trong manifest cũ mà không có trong manifest mới thì bị xoá.

const (
	manifestName   = "release-manifest.txt"
	newExeName     = "TikTokAuto.new.exe"
	oldExeName     = "TikTokAuto.old.exe"
	exeName        = "TikTokAuto.exe"
	maxUnpackBytes = 4 << 30 // chống zip bomb
	maxZipEntries  = 200000
	keepSnapshots  = 2
)

// protectedTop: thư mục gốc không bao giờ bị cập nhật/xoá.
var protectedTop = map[string]bool{
	"runtime": true, "storage": true, "du-lieu": true, "dist": true,
}

// protectedAnySegment: tên thư mục ở bất kỳ độ sâu nào đều là dữ liệu/môi trường của người dùng.
var protectedAnySegment = map[string]bool{
	".git": true, "node_modules": true, ".venv": true, "venv": true, "__pycache__": true,
}

// protectedPrefixes: dữ liệu/cấu hình riêng của Xưởng Video nằm cạnh mã (dữ liệu chính ở du-lieu/xuong-video, đã được bảo vệ).
var protectedPrefixes = []string{
	"xuong-video/tai-khoan/", "xuong-video/config.json", "xuong-video/remotion/out/", "xuong-video/remotion/.cache/",
}

// NormalizeRel kiểm tra và chuẩn hoá một đường dẫn tương đối trong gói/manifest.
// Từ chối: tuyệt đối, ổ đĩa/luồng (":"), "..", ký tự NUL/điều khiển, đoạn rỗng hoặc ".".
func NormalizeRel(name string) (string, error) {
	n := strings.ReplaceAll(name, "\\", "/")
	n = strings.TrimSuffix(n, "/")
	if n == "" {
		return "", errors.New("đường dẫn rỗng")
	}
	if strings.HasPrefix(n, "/") || strings.Contains(n, ":") {
		return "", fmt.Errorf("đường dẫn tuyệt đối/không hợp lệ: %q", name)
	}
	for _, r := range n {
		if r < 0x20 {
			return "", fmt.Errorf("ký tự điều khiển trong đường dẫn: %q", name)
		}
	}
	for _, seg := range strings.Split(n, "/") {
		if seg == "" || seg == "." || seg == ".." {
			return "", fmt.Errorf("đường dẫn không an toàn: %q", name)
		}
		if strings.TrimRight(seg, " .") != seg {
			return "", fmt.Errorf("đường dẫn không an toàn (dấu chấm/khoảng trắng cuối): %q", name)
		}
	}
	if path.Clean(n) != n {
		return "", fmt.Errorf("đường dẫn không chuẩn: %q", name)
	}
	return n, nil
}

// IsProtected: đường dẫn (đã chuẩn hoá) mà bản cập nhật không được ghi/xoá.
func IsProtected(rel string) bool {
	low := strings.ToLower(rel)
	segs := strings.Split(low, "/")
	if protectedTop[segs[0]] {
		return true
	}
	for _, s := range segs {
		if protectedAnySegment[s] {
			return true
		}
	}
	base := segs[len(segs)-1]
	if base == ".env" || (strings.HasPrefix(base, ".env.") && base != ".env.example") {
		return true
	}
	if len(segs) == 1 && (base == strings.ToLower(exeName) || base == strings.ToLower(oldExeName)) {
		return true
	}
	for _, p := range protectedPrefixes {
		if strings.HasPrefix(low, p) {
			return true
		}
	}
	return false
}

// ParseManifest đọc manifest: trả danh sách hợp lệ (đã chuẩn hoá, bỏ trùng, sắp xếp) và các dòng bị từ chối.
func ParseManifest(b []byte) (files []string, bad []string) {
	seen := map[string]bool{}
	sc := bufio.NewScanner(bytes.NewReader(bytes.TrimPrefix(b, []byte{0xEF, 0xBB, 0xBF})))
	sc.Buffer(make([]byte, 64<<10), 1<<20)
	for sc.Scan() {
		ln := strings.TrimSpace(sc.Text())
		if ln == "" || strings.HasPrefix(ln, "#") {
			continue
		}
		rel, err := NormalizeRel(ln)
		if err != nil {
			bad = append(bad, ln)
			continue
		}
		if !seen[rel] {
			seen[rel] = true
			files = append(files, rel)
		}
	}
	sort.Strings(files)
	return files, bad
}

// StaleFiles: file có ở bản cũ mà không có ở bản mới, đã loại đường dẫn được bảo vệ.
func StaleFiles(oldM, newM []string) []string {
	in := map[string]bool{}
	for _, f := range newM {
		in[strings.ToLower(f)] = true
	}
	var out []string
	for _, f := range oldM {
		if in[strings.ToLower(f)] || IsProtected(f) || f == manifestName {
			continue
		}
		out = append(out, f)
	}
	return out
}

// resolveUnder ghép root+rel và bảo đảm kết quả (sau khi giải symlink/junction của thư mục cha) vẫn nằm trong root.
func resolveUnder(root, rel string) (string, error) {
	n, err := NormalizeRel(rel)
	if err != nil {
		return "", err
	}
	full := filepath.Join(root, filepath.FromSlash(n))
	rootReal, err := filepath.EvalSymlinks(root)
	if err != nil {
		return "", err
	}
	// giải symlink cho phần thư mục cha tồn tại sâu nhất
	dir := filepath.Dir(full)
	for {
		if real, err := filepath.EvalSymlinks(dir); err == nil {
			rel2, err := filepath.Rel(rootReal, real)
			if err != nil || rel2 == ".." || strings.HasPrefix(rel2, ".."+string(filepath.Separator)) {
				return "", fmt.Errorf("đường dẫn thoát khỏi thư mục cài đặt: %s", rel)
			}
			break
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", fmt.Errorf("không xác định được thư mục cha của %s", rel)
		}
		dir = parent
	}
	if r, err := filepath.Rel(root, full); err != nil || r == ".." || strings.HasPrefix(r, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("đường dẫn thoát khỏi thư mục cài đặt: %s", rel)
	}
	return full, nil
}

// SafeDelete xoá một file thường trong root. Từ chối đường dẫn được bảo vệ / ngoài root / không phải file thường.
func SafeDelete(root, rel string) error {
	n, err := NormalizeRel(rel)
	if err != nil {
		return err
	}
	if IsProtected(n) {
		return fmt.Errorf("đường dẫn được bảo vệ: %s", n)
	}
	full, err := resolveUnder(root, n)
	if err != nil {
		return err
	}
	st, err := os.Lstat(full)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	if !st.Mode().IsRegular() {
		return fmt.Errorf("không phải file thường, bỏ qua: %s", n)
	}
	if err := os.Remove(full); err != nil {
		return err
	}
	// dọn thư mục rỗng, dừng ở root hoặc thư mục được bảo vệ
	rootClean := filepath.Clean(root)
	for d := filepath.Dir(full); d != rootClean && strings.HasPrefix(d, rootClean); d = filepath.Dir(d) {
		if r, err := filepath.Rel(rootClean, d); err != nil || IsProtected(filepath.ToSlash(r)) {
			break
		}
		if os.Remove(d) != nil { // không rỗng
			break
		}
	}
	return nil
}

// DeleteStale xoá danh sách file cũ; lỗi từng file chỉ ghi log. Trả số file đã xoá.
func DeleteStale(root string, files []string, log *Logger) int {
	n := 0
	for _, f := range files {
		if _, err := os.Lstat(filepath.Join(root, filepath.FromSlash(f))); err != nil {
			continue
		}
		if err := SafeDelete(root, f); err != nil {
			log.Printf("Cập nhật: không xoá được %s: %v", f, err)
			continue
		}
		n++
	}
	return n
}

// ---- SHA-256 ----

// FileSHA256 trả hex sha256 của file.
func FileSHA256(p string) (string, error) {
	f, err := os.Open(p)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

var sha256RE = regexp.MustCompile(`(?i)\b[0-9a-f]{64}\b`)

// ParseSHA256File lấy mã sha256 từ nội dung file .sha256 ("<hex>  tên" hoặc "<hex>").
func ParseSHA256File(b []byte) (string, error) {
	m := sha256RE.Find(b)
	if m == nil {
		return "", errors.New("file .sha256 không chứa mã sha256 hợp lệ")
	}
	return strings.ToLower(string(m)), nil
}

// VerifySHA256 so khớp file với mã mong đợi; lệch => lỗi (bên gọi phải huỷ cập nhật).
func VerifySHA256(p, want string) error {
	got, err := FileSHA256(p)
	if err != nil {
		return err
	}
	if !strings.EqualFold(got, strings.TrimSpace(want)) {
		return fmt.Errorf("sai mã sha256 (gói tải về bị hỏng hoặc bị thay đổi): cần %s, nhận %s", want, got)
	}
	return nil
}

// ---- Zip ----

// ZipPackage là gói phát hành đã mở và kiểm tra (chưa ghi gì ra đĩa).
type ZipPackage struct {
	zr       *zip.ReadCloser
	entries  map[string]*zip.File // theo đường dẫn đã chuẩn hoá
	Manifest []string
	Version  string
}

func (p *ZipPackage) Close() { p.zr.Close() }

// OpenPackage mở zip và kiểm tra: tên file (zip-slip), symlink, kích thước, manifest, VERSION.
// Bất kỳ tên độc hại nào => lỗi cho cả gói.
func OpenPackage(zipPath string) (*ZipPackage, error) {
	zr, err := zip.OpenReader(zipPath)
	if err != nil {
		return nil, fmt.Errorf("không mở được gói cập nhật: %w", err)
	}
	p := &ZipPackage{zr: zr, entries: map[string]*zip.File{}}
	fail := func(e error) (*ZipPackage, error) { zr.Close(); return nil, e }
	if len(zr.File) > maxZipEntries {
		return fail(errors.New("gói có quá nhiều file"))
	}
	var total uint64
	for _, f := range zr.File {
		if strings.HasSuffix(f.Name, "/") || f.FileInfo().IsDir() {
			if _, err := NormalizeRel(f.Name); err != nil {
				return fail(fmt.Errorf("gói chứa đường dẫn độc hại: %w", err))
			}
			continue
		}
		rel, err := NormalizeRel(f.Name)
		if err != nil {
			return fail(fmt.Errorf("gói chứa đường dẫn độc hại: %w", err))
		}
		if f.Mode()&os.ModeSymlink != 0 {
			return fail(fmt.Errorf("gói chứa liên kết tượng trưng: %s", rel))
		}
		total += f.UncompressedSize64
		if total > maxUnpackBytes {
			return fail(errors.New("gói giải nén quá lớn"))
		}
		key := strings.ToLower(rel)
		if _, dup := p.entries[key]; dup {
			return fail(fmt.Errorf("gói có file trùng tên: %s", rel))
		}
		p.entries[key] = f
	}
	mf, ok := p.entries[manifestName]
	if !ok {
		return fail(fmt.Errorf("gói không có %s", manifestName))
	}
	b, err := readZipFile(mf, 64<<20)
	if err != nil {
		return fail(err)
	}
	files, bad := ParseManifest(b)
	if len(bad) > 0 {
		return fail(fmt.Errorf("%s có đường dẫn không hợp lệ: %q", manifestName, bad[0]))
	}
	for _, rel := range files {
		if _, ok := p.entries[strings.ToLower(rel)]; !ok && rel != manifestName {
			return fail(fmt.Errorf("manifest liệt kê %s nhưng gói không có file này", rel))
		}
	}
	p.Manifest = files
	if vf, ok := p.entries["version"]; ok {
		vb, err := readZipFile(vf, 256)
		if err != nil {
			return fail(err)
		}
		p.Version = strings.TrimSpace(string(vb))
	}
	if _, err := ParseVersion(p.Version); err != nil {
		return fail(errors.New("gói thiếu file VERSION hợp lệ"))
	}
	return p, nil
}

func readZipFile(f *zip.File, limit int64) ([]byte, error) {
	rc, err := f.Open()
	if err != nil {
		return nil, err
	}
	defer rc.Close()
	b, err := io.ReadAll(io.LimitReader(rc, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(b)) > limit {
		return nil, fmt.Errorf("%s quá lớn", f.Name)
	}
	return b, nil
}

// ManifestBytes trả nội dung manifest gốc trong gói.
func (p *ZipPackage) ManifestBytes() ([]byte, error) {
	return readZipFile(p.entries[manifestName], 64<<20)
}

// Extract ghi các file trong manifest (trừ đường dẫn được bảo vệ) vào root, mỗi file ghi tạm rồi đổi tên.
// Trả danh sách file đã ghi.
func (p *ZipPackage) Extract(root string, log *Logger) ([]string, error) {
	var written []string
	for _, rel := range p.Manifest {
		if IsProtected(rel) {
			log.Printf("Cập nhật: bỏ qua đường dẫn được bảo vệ trong gói: %s", rel)
			continue
		}
		if rel == manifestName {
			continue // ghi riêng vào runtime/
		}
		f := p.entries[strings.ToLower(rel)]
		dest, err := resolveUnder(root, rel)
		if err != nil {
			return written, err
		}
		if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
			return written, err
		}
		if err := writeZipEntry(f, dest); err != nil {
			return written, fmt.Errorf("không ghi được %s: %w", rel, err)
		}
		written = append(written, rel)
	}
	return written, nil
}

func writeZipEntry(f *zip.File, dest string) error {
	rc, err := f.Open()
	if err != nil {
		return err
	}
	defer rc.Close()
	tmp := dest + ".tta-new"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	n, err := io.Copy(out, io.LimitReader(rc, int64(f.UncompressedSize64)+1))
	if cerr := out.Close(); err == nil {
		err = cerr
	}
	if err == nil && n != int64(f.UncompressedSize64) {
		err = errors.New("kích thước giải nén không khớp")
	}
	if err != nil {
		os.Remove(tmp)
		return err
	}
	if err := os.Rename(tmp, dest); err != nil {
		os.Remove(tmp)
		return err
	}
	return nil
}

// ---- Snapshot / rollback ----

type snapshotMeta struct {
	Version   string    `json:"version"`
	CreatedAt time.Time `json:"created_at"`
	Files     []string  `json:"files"`
	HadManif  bool      `json:"had_manifest"`
	Backup    string    `json:"db_backup,omitempty"`
}

// SnapshotRoot: nơi giữ các bản cũ (runtime/ban-cu/<phiên-bản>/).
func SnapshotRoot(root string) string { return filepath.Join(root, "runtime", "ban-cu") }

// ManifestPath: manifest của bản đang cài.
func ManifestPath(root string) string { return filepath.Join(root, "runtime", manifestName) }

var verDirRE = regexp.MustCompile(`[^0-9A-Za-z.+-]`)

func snapDirFor(root, ver string) string {
	return filepath.Join(SnapshotRoot(root), verDirRE.ReplaceAllString(ver, "_"))
}

// collectCodeFiles: file mã nguồn hiện có để chụp. Có manifest cũ thì dùng nó; không thì duyệt thư mục (bỏ phần được bảo vệ).
func collectCodeFiles(root string, oldManifest []string, haveManifest bool) []string {
	var out []string
	if haveManifest {
		for _, f := range oldManifest {
			if IsProtected(f) {
				continue
			}
			if st, err := os.Lstat(filepath.Join(root, filepath.FromSlash(f))); err == nil && st.Mode().IsRegular() {
				out = append(out, f)
			}
		}
		return out
	}
	filepath.WalkDir(root, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		r, e := filepath.Rel(root, p)
		if e != nil || r == "." {
			return nil
		}
		rel := filepath.ToSlash(r)
		if IsProtected(rel) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if d.Type().IsRegular() {
			if n, err := NormalizeRel(rel); err == nil {
				out = append(out, n)
			}
		}
		return nil
	})
	sort.Strings(out)
	return out
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	tmp := dst + ".tta-new"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, in)
	if cerr := out.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		os.Remove(tmp)
		return err
	}
	return os.Rename(tmp, dst)
}

// TakeSnapshot chụp mã hiện tại vào runtime/ban-cu/<ver>/ (files/ + meta.json + manifest.txt).
func TakeSnapshot(root, ver, dbBackup string) (string, error) {
	dir := snapDirFor(root, ver)
	if err := os.RemoveAll(dir); err != nil {
		return "", err
	}
	mb, merr := os.ReadFile(ManifestPath(root))
	oldM, _ := ParseManifest(mb)
	files := collectCodeFiles(root, oldM, merr == nil)
	for _, f := range files {
		if err := copyFile(filepath.Join(root, filepath.FromSlash(f)), filepath.Join(dir, "files", filepath.FromSlash(f))); err != nil {
			os.RemoveAll(dir)
			return "", fmt.Errorf("không chụp được %s: %w", f, err)
		}
	}
	if merr == nil {
		if err := os.WriteFile(filepath.Join(dir, "manifest.txt"), mb, 0o644); err != nil {
			os.RemoveAll(dir)
			return "", err
		}
	}
	meta, _ := json.Marshal(snapshotMeta{Version: ver, CreatedAt: time.Now(), Files: files, HadManif: merr == nil, Backup: dbBackup})
	if err := os.WriteFile(filepath.Join(dir, "meta.json"), meta, 0o644); err != nil {
		os.RemoveAll(dir)
		return "", err
	}
	return dir, nil
}

func readSnapshotMeta(dir string) (*snapshotMeta, error) {
	b, err := os.ReadFile(filepath.Join(dir, "meta.json"))
	if err != nil {
		return nil, err
	}
	var m snapshotMeta
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

// RestoreSnapshot đưa mã về như lúc chụp: chép lại file đã chụp, xoá file mà bản mới thêm vào
// (có trong manifest mới nhưng không có trong snapshot), trả lại manifest cũ.
func RestoreSnapshot(root, dir string, newManifest []string, log *Logger) error {
	meta, err := readSnapshotMeta(dir)
	if err != nil {
		return fmt.Errorf("snapshot hỏng: %w", err)
	}
	had := map[string]bool{}
	for _, f := range meta.Files {
		had[strings.ToLower(f)] = true
	}
	var firstErr error
	for _, f := range meta.Files {
		n, err := NormalizeRel(f)
		if err != nil || IsProtected(n) {
			continue
		}
		dest, err := resolveUnder(root, n)
		if err == nil {
			err = copyFile(filepath.Join(dir, "files", filepath.FromSlash(n)), dest)
		}
		if err != nil {
			log.Printf("Khôi phục: lỗi %s: %v", n, err)
			if firstErr == nil {
				firstErr = fmt.Errorf("không khôi phục được %s: %w", n, err)
			}
		}
	}
	var added []string
	for _, f := range newManifest {
		if !had[strings.ToLower(f)] && f != manifestName {
			added = append(added, f)
		}
	}
	DeleteStale(root, added, log)
	mp := ManifestPath(root)
	if b, err := os.ReadFile(filepath.Join(dir, "manifest.txt")); err == nil {
		os.WriteFile(mp, b, 0o644)
	} else {
		os.Remove(mp)
	}
	return firstErr
}

// SnapshotInfo mô tả một bản cũ đang giữ.
type SnapshotInfo struct {
	Version   string    `json:"version"`
	CreatedAt time.Time `json:"created_at"`
	Dir       string    `json:"-"`
	Backup    string    `json:"db_backup,omitempty"`
}

// ListSnapshots trả các bản cũ, mới nhất trước.
func ListSnapshots(root string) []SnapshotInfo {
	ents, _ := os.ReadDir(SnapshotRoot(root))
	var out []SnapshotInfo
	for _, e := range ents {
		if !e.IsDir() {
			continue
		}
		dir := filepath.Join(SnapshotRoot(root), e.Name())
		if m, err := readSnapshotMeta(dir); err == nil {
			out = append(out, SnapshotInfo{Version: m.Version, CreatedAt: m.CreatedAt, Dir: dir, Backup: m.Backup})
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].CreatedAt.After(out[j].CreatedAt) })
	return out
}

// PruneSnapshots giữ keep bản mới nhất.
func PruneSnapshots(root string, keep int) {
	l := ListSnapshots(root)
	for i := keep; i < len(l); i++ {
		os.RemoveAll(l[i].Dir)
	}
}

// fileHash: sha256 của file hoặc "" nếu không có (để biết requirements/package-lock có đổi không).
func fileHash(p string) string {
	h, err := FileSHA256(p)
	if err != nil {
		return ""
	}
	return h
}
