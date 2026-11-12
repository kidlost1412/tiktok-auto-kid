package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	placeholderRepo = "CHUA_CAU_HINH/tiktok-auto-kid"
	checkCacheTTL   = time.Hour
	assetPrefix     = "tiktok-auto-kid-"
)

var repoRE = regexp.MustCompile(`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`)

// UpdateRepo trả "owner/repo" từ UPDATE_REPO (môi trường > .env > services.json vars). Rỗng nếu chưa cấu hình.
func UpdateRepo() string {
	v, _ := lookupVar("UPDATE_REPO")
	v = strings.TrimSpace(v)
	if v == "" || strings.EqualFold(v, placeholderRepo) || strings.HasPrefix(strings.ToUpper(v), "CHUA_CAU_HINH/") || !repoRE.MatchString(v) || strings.HasPrefix(v, ".") || strings.Contains(v, "/.") {
		return ""
	}
	return v
}

// ReleaseInfo là bản phát hành mới nhất.
type ReleaseInfo struct {
	Version     string `json:"version"`
	Tag         string `json:"tag"`
	Notes       string `json:"notes"`
	PageURL     string `json:"page_url"`
	PublishedAt string `json:"published_at"`
	ZipName     string `json:"zip_name"`
	ZipURL      string `json:"zip_url"`
	ZipSize     int64  `json:"zip_size"`
	SHAURL      string `json:"sha_url"`
}

// checkCache là nội dung runtime/update-check.json.
type checkCache struct {
	Repo      string       `json:"repo"`
	CheckedAt time.Time    `json:"checked_at"`
	Latest    *ReleaseInfo `json:"latest,omitempty"`
	Error     string       `json:"error,omitempty"`
	RetryAt   time.Time    `json:"retry_at,omitempty"` // bị giới hạn tốc độ: không gọi lại trước mốc này
}

type ghRelease struct {
	TagName     string `json:"tag_name"`
	Body        string `json:"body"`
	HTMLURL     string `json:"html_url"`
	PublishedAt string `json:"published_at"`
	Draft       bool   `json:"draft"`
	Prerelease  bool   `json:"prerelease"`
	Assets      []struct {
		Name string `json:"name"`
		URL  string `json:"browser_download_url"`
		Size int64  `json:"size"`
	} `json:"assets"`
}

// allowedDownloadHost: chỉ tải từ GitHub (kể cả CDN của GitHub).
var allowedDownloadHost = isGitHubHost

func isGitHubHost(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "https" {
		return false
	}
	h := strings.ToLower(u.Hostname())
	return h == "github.com" || h == "api.github.com" || strings.HasSuffix(h, ".githubusercontent.com") || strings.HasSuffix(h, ".github.com")
}

// ParseRelease đổi JSON của GitHub thành ReleaseInfo; lỗi nếu thiếu asset zip/sha256 đúng tên.
func ParseRelease(b []byte) (*ReleaseInfo, error) {
	var r ghRelease
	if err := json.Unmarshal(b, &r); err != nil {
		return nil, fmt.Errorf("phản hồi GitHub không đọc được: %w", err)
	}
	ver := strings.TrimPrefix(strings.TrimPrefix(r.TagName, "v"), "V")
	if _, err := ParseVersion(ver); err != nil {
		return nil, fmt.Errorf("tên bản phát hành không phải số phiên bản: %q", r.TagName)
	}
	zipName := assetPrefix + ver + ".zip"
	info := &ReleaseInfo{Version: ver, Tag: r.TagName, Notes: r.Body, PageURL: r.HTMLURL, PublishedAt: r.PublishedAt}
	for _, a := range r.Assets {
		switch a.Name {
		case zipName:
			info.ZipName, info.ZipURL, info.ZipSize = a.Name, a.URL, a.Size
		case zipName + ".sha256":
			info.SHAURL = a.URL
		}
	}
	if info.ZipURL == "" || info.SHAURL == "" {
		return nil, fmt.Errorf("bản %s thiếu file %s hoặc %s.sha256", ver, zipName, zipName)
	}
	if !allowedDownloadHost(info.ZipURL) || !allowedDownloadHost(info.SHAURL) {
		return nil, errors.New("địa chỉ tải không thuộc GitHub, từ chối")
	}
	return info, nil
}

func cachePath(root string) string { return filepath.Join(root, "runtime", "update-check.json") }

func loadCheckCache(root string) *checkCache {
	b, err := os.ReadFile(cachePath(root))
	if err != nil {
		return nil
	}
	var c checkCache
	if json.Unmarshal(b, &c) != nil {
		return nil
	}
	return &c
}

func saveCheckCache(root string, c *checkCache) {
	if b, err := json.Marshal(c); err == nil {
		os.WriteFile(cachePath(root), b, 0o644)
	}
}

// UpdateChecker hỏi GitHub (không cần token), lưu cache 1 giờ, xử lý giới hạn tốc độ.
type UpdateChecker struct {
	Root    string
	APIBase string // mặc định https://api.github.com (để kiểm thử)
	HTTP    *http.Client
	Now     func() time.Time
}

func (u *UpdateChecker) now() time.Time {
	if u.Now != nil {
		return u.Now()
	}
	return time.Now()
}

func (u *UpdateChecker) client() *http.Client {
	if u.HTTP != nil {
		return u.HTTP
	}
	return &http.Client{Timeout: 20 * time.Second}
}

// Check trả bản mới nhất (từ cache nếu còn hạn và !force). Chưa cấu hình kho => errNotConfigured.
func (u *UpdateChecker) Check(force bool) (*checkCache, error) {
	repo := UpdateRepo()
	if repo == "" {
		return nil, errNotConfigured
	}
	old := loadCheckCache(u.Root)
	if old != nil && old.Repo == repo {
		if !old.RetryAt.IsZero() && u.now().Before(old.RetryAt) {
			return old, nil // đang bị giới hạn tốc độ
		}
		if !force && u.now().Sub(old.CheckedAt) < checkCacheTTL && old.Error == "" {
			return old, nil
		}
		if !force && u.now().Sub(old.CheckedAt) < 10*time.Minute { // lỗi gần đây: đừng gọi dồn dập
			return old, nil
		}
	}
	c := &checkCache{Repo: repo, CheckedAt: u.now()}
	if old != nil && old.Repo == repo {
		c.Latest = old.Latest // giữ kết quả cũ nếu lần này lỗi
	}
	base := u.APIBase
	if base == "" {
		base = "https://api.github.com"
	}
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, base+"/repos/"+repo+"/releases/latest", nil)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("User-Agent", "TikTokAutoKid-Updater")
	resp, err := u.client().Do(req)
	if err != nil {
		c.Error = "Không kết nối được GitHub (kiểm tra mạng)."
		saveCheckCache(u.Root, c)
		return c, nil
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	switch {
	case resp.StatusCode == http.StatusNotFound:
		c.Latest, c.Error = nil, "Kho "+repo+" chưa có bản phát hành nào (hoặc kho không công khai)."
	case resp.StatusCode == http.StatusForbidden || resp.StatusCode == http.StatusTooManyRequests:
		reset := u.now().Add(30 * time.Minute)
		if v := resp.Header.Get("X-RateLimit-Reset"); v != "" {
			if sec, err := strconv.ParseInt(v, 10, 64); err == nil {
				reset = time.Unix(sec, 0)
			}
		}
		if v := resp.Header.Get("Retry-After"); v != "" {
			if sec, err := strconv.Atoi(v); err == nil {
				reset = u.now().Add(time.Duration(sec) * time.Second)
			}
		}
		c.RetryAt = reset
		c.Error = "GitHub đang giới hạn lượt kiểm tra, sẽ thử lại sau " + reset.Local().Format("15:04") + "."
	case resp.StatusCode != http.StatusOK:
		c.Error = fmt.Sprintf("GitHub trả lỗi %d.", resp.StatusCode)
	default:
		var rel ghRelease
		if json.Unmarshal(body, &rel) == nil && (rel.Draft || rel.Prerelease) {
			c.Error = "Bản mới nhất là bản nháp/thử nghiệm, bỏ qua."
			break
		}
		info, err := ParseRelease(body)
		if err != nil {
			c.Error = err.Error()
		} else {
			c.Latest, c.Error = info, ""
		}
	}
	saveCheckCache(u.Root, c)
	return c, nil
}

var errNotConfigured = errors.New("chưa cấu hình kho cập nhật (UPDATE_REPO)")

// DownloadRelease tải zip + sha256 vào dir, kiểm tra mã. Trả đường dẫn zip đã xác minh.
// Sai mã => xoá file và trả lỗi.
func DownloadRelease(ctx context.Context, rel *ReleaseInfo, dir string, hc *http.Client, progress func(done, total int64)) (string, error) {
	if !allowedDownloadHost(rel.ZipURL) || !allowedDownloadHost(rel.SHAURL) {
		return "", errors.New("địa chỉ tải không thuộc GitHub, từ chối")
	}
	if hc == nil {
		hc = &http.Client{}
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	get := func(u string) (*http.Response, error) {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
		req.Header.Set("User-Agent", "TikTokAutoKid-Updater")
		resp, err := hc.Do(req)
		if err != nil {
			return nil, err
		}
		if resp.StatusCode != http.StatusOK {
			resp.Body.Close()
			return nil, fmt.Errorf("tải %s lỗi HTTP %d", u, resp.StatusCode)
		}
		return resp, nil
	}
	resp, err := get(rel.SHAURL)
	if err != nil {
		return "", err
	}
	shaBytes, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	resp.Body.Close()
	want, err := ParseSHA256File(shaBytes)
	if err != nil {
		return "", err
	}
	zr, err := get(rel.ZipURL)
	if err != nil {
		return "", err
	}
	defer zr.Body.Close()
	dest := filepath.Join(dir, filepath.Base(rel.ZipName))
	f, err := os.Create(dest)
	if err != nil {
		return "", err
	}
	total := zr.ContentLength
	if total <= 0 {
		total = rel.ZipSize
	}
	buf := make([]byte, 256<<10)
	var done int64
	for {
		n, rerr := zr.Body.Read(buf)
		if n > 0 {
			if _, werr := f.Write(buf[:n]); werr != nil {
				f.Close()
				os.Remove(dest)
				return "", werr
			}
			done += int64(n)
			if progress != nil {
				progress(done, total)
			}
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			f.Close()
			os.Remove(dest)
			return "", rerr
		}
	}
	if err := f.Close(); err != nil {
		os.Remove(dest)
		return "", err
	}
	if err := VerifySHA256(dest, want); err != nil {
		os.Remove(dest)
		return "", err
	}
	return dest, nil
}
