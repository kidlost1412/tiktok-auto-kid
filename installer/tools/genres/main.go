// genres tạo rsrc_windows_amd64.syso cho trình cài: biểu tượng + manifest (DPI, UTF-8) + thông tin phiên bản.
// Chạy trong thư mục installer:  go run ./tools/genres -ico assets/icon.ico -manifest assets/app.manifest -version 1.1.3 -o rsrc_windows_amd64.syso
package main

import (
	"bytes"
	"encoding/binary"
	"flag"
	"fmt"
	"io"
	"os"
	"reflect"
	"strconv"
	"strings"
	"unicode/utf16"

	"github.com/akavel/rsrc/binutil"
	"github.com/akavel/rsrc/coff"
	"github.com/akavel/rsrc/ico"
)

const rtVersion = 16

type grpIconDir struct {
	ico.ICONDIR
	Entries []grpIconDirEntry
}

func (g grpIconDir) Size() int64 {
	return int64(binary.Size(g.ICONDIR) + len(g.Entries)*binary.Size(g.Entries[0]))
}

type grpIconDirEntry struct {
	ico.IconDirEntryCommon
	Id uint16
}

func u16(s string) []byte {
	u := utf16.Encode([]rune(s))
	u = append(u, 0)
	b := make([]byte, len(u)*2)
	for i, c := range u {
		binary.LittleEndian.PutUint16(b[i*2:], c)
	}
	return b
}

func pad4(b []byte) []byte {
	for len(b)%4 != 0 {
		b = append(b, 0)
	}
	return b
}

// block dựng một khối VERSIONINFO: header + khoá + giá trị + con.
func block(key string, value []byte, valueLen int, typ int, children []byte) []byte {
	var b []byte
	b = append(b, 0, 0) // wLength (điền sau)
	b = binary.LittleEndian.AppendUint16(b, uint16(valueLen))
	b = binary.LittleEndian.AppendUint16(b, uint16(typ))
	b = append(b, u16(key)...)
	b = pad4(b)
	b = append(b, value...)
	b = pad4(b)
	b = append(b, children...)
	binary.LittleEndian.PutUint16(b[0:], uint16(len(b)))
	return b
}

func versionInfo(ver string, strs [][2]string) []byte {
	parts := strings.Split(ver, ".")
	n := [4]uint16{}
	for i := 0; i < 4 && i < len(parts); i++ {
		v, _ := strconv.Atoi(parts[i])
		n[i] = uint16(v)
	}
	ffi := new(bytes.Buffer)
	for _, v := range []uint32{0xFEEF04BD, 0x00010000,
		uint32(n[0])<<16 | uint32(n[1]), uint32(n[2])<<16 | uint32(n[3]),
		uint32(n[0])<<16 | uint32(n[1]), uint32(n[2])<<16 | uint32(n[3]),
		0x3F, 0, 0x00040004, 1, 0, 0, 0} {
		_ = binary.Write(ffi, binary.LittleEndian, v)
	}
	var st []byte
	for _, kv := range strs {
		v := u16(kv[1])
		st = append(st, pad4(block(kv[0], v, len(v)/2, 1, nil))...)
	}
	table := block("040904B0", nil, 0, 1, st)
	sfi := block("StringFileInfo", nil, 0, 1, pad4(table))
	trans := []byte{0x09, 0x04, 0xB0, 0x04}
	vr := block("Translation", trans, 4, 0, nil)
	vfi := block("VarFileInfo", nil, 0, 1, pad4(vr))
	children := append(pad4(sfi), pad4(vfi)...)
	return block("VS_VERSION_INFO", ffi.Bytes(), 52, 0, children)
}

func main() {
	icoPath := flag.String("ico", "", "file .ico")
	manifest := flag.String("manifest", "", "file manifest")
	ver := flag.String("version", "1.0.0", "phiên bản")
	out := flag.String("o", "rsrc_windows_amd64.syso", "file .syso đầu ra")
	flag.Parse()

	c := coff.NewRSRC()
	if err := c.Arch("amd64"); err != nil {
		fail(err)
	}
	// Mỗi loại tài nguyên: id tăng dần.
	grpID := uint16(1)
	nextIcon := uint16(2)
	if *manifest != "" {
		m, err := binutil.SizedOpen(*manifest)
		if err != nil {
			fail(err)
		}
		defer m.Close()
		c.AddResource(coff.RT_MANIFEST, 1, m)
	}
	if *icoPath != "" {
		f, err := os.Open(*icoPath)
		if err != nil {
			fail(err)
		}
		defer f.Close()
		icons, err := ico.DecodeHeaders(f)
		if err != nil {
			fail(err)
		}
		group := grpIconDir{ICONDIR: ico.ICONDIR{Type: 1, Count: uint16(len(icons))}}
		for _, ic := range icons {
			id := nextIcon
			nextIcon++
			r := io.NewSectionReader(f, int64(ic.ImageOffset), int64(ic.BytesInRes))
			c.AddResource(coff.RT_ICON, id, r)
			group.Entries = append(group.Entries, grpIconDirEntry{ic.IconDirEntryCommon, id})
		}
		c.AddResource(coff.RT_GROUP_ICON, grpID, group)
	}
	vi := versionInfo(*ver, [][2]string{
		{"CompanyName", "Kid"},
		{"FileDescription", "Trình cài đặt TikTok Auto Kid"},
		{"FileVersion", *ver},
		{"InternalName", "TikTokAutoKid-Setup"},
		{"LegalCopyright", "Kid"},
		{"OriginalFilename", "TikTokAutoKid-Setup.exe"},
		{"ProductName", "TikTok Auto Kid"},
		{"ProductVersion", *ver},
	})
	c.AddResource(rtVersion, 1, bytes.NewReader(vi))
	c.Freeze()

	f, err := os.Create(*out)
	if err != nil {
		fail(err)
	}
	defer f.Close()
	w := binutil.Writer{W: f}
	binutil.Walk(c, func(v reflect.Value, path string) error {
		if binutil.Plain(v.Kind()) {
			w.WriteLE(v.Interface())
			return nil
		}
		if vv, ok := v.Interface().(binutil.SizedReader); ok {
			w.WriteFromSized(vv)
			return binutil.WALK_SKIP
		}
		return nil
	})
	if w.Err != nil {
		fail(w.Err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
