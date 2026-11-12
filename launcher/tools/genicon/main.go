// genicon tạo assets/icon.ico (16/32/48 px, BMP 32-bit). Chạy: go run ./tools/genicon assets/icon.ico
package main

import (
	"bytes"
	"encoding/binary"
	"math"
	"os"
)

type px struct{ r, g, b, a uint8 }

func draw(n int) []px {
	img := make([]px, n*n)
	f := float64(n)
	rad := f * 0.22
	inRound := func(x, y float64) bool {
		cx := math.Min(math.Max(x, rad), f-rad)
		cy := math.Min(math.Max(y, rad), f-rad)
		return math.Hypot(x-cx, y-cy) <= rad
	}
	// chữ T: thanh ngang + thanh dọc
	inT := func(x, y, dx, dy float64) bool {
		x -= dx
		y -= dy
		top := y > f*0.22 && y < f*0.38 && x > f*0.2 && x < f*0.8
		stem := x > f*0.42 && x < f*0.58 && y > f*0.22 && y < f*0.80
		return top || stem
	}
	for yy := 0; yy < n; yy++ {
		for xx := 0; xx < n; xx++ {
			x, y := float64(xx)+0.5, float64(yy)+0.5
			if !inRound(x, y) {
				continue
			}
			p := px{16, 16, 20, 255}
			o := f * 0.04
			if inT(x, y, -o, o) {
				p = px{37, 244, 238, 255} // cyan
			}
			if inT(x, y, o, -o) {
				p = px{254, 44, 85, 255} // đỏ hồng
			}
			if inT(x, y, 0, 0) {
				p = px{255, 255, 255, 255}
			}
			img[yy*n+xx] = p
		}
	}
	return img
}

func dib(n int) []byte {
	var b bytes.Buffer
	w := func(v any) { binary.Write(&b, binary.LittleEndian, v) }
	w(uint32(40))
	w(int32(n))
	w(int32(n * 2))
	w(uint16(1))
	w(uint16(32))
	w(uint32(0))
	w(uint32(n * n * 4))
	w(int32(0))
	w(int32(0))
	w(uint32(0))
	w(uint32(0))
	img := draw(n)
	for y := n - 1; y >= 0; y-- {
		for x := 0; x < n; x++ {
			p := img[y*n+x]
			b.Write([]byte{p.b, p.g, p.r, p.a})
		}
	}
	mask := ((n + 31) / 32) * 4
	b.Write(make([]byte, mask*n))
	return b.Bytes()
}

func main() {
	out := "assets/icon.ico"
	if len(os.Args) > 1 {
		out = os.Args[1]
	}
	sizes := []int{16, 32, 48}
	var b bytes.Buffer
	binary.Write(&b, binary.LittleEndian, [3]uint16{0, 1, uint16(len(sizes))})
	var datas [][]byte
	off := 6 + 16*len(sizes)
	for _, n := range sizes {
		d := dib(n)
		datas = append(datas, d)
		b.Write([]byte{byte(n), byte(n), 0, 0})
		binary.Write(&b, binary.LittleEndian, [2]uint16{1, 32})
		binary.Write(&b, binary.LittleEndian, uint32(len(d)))
		binary.Write(&b, binary.LittleEndian, uint32(off))
		off += len(d)
	}
	for _, d := range datas {
		b.Write(d)
	}
	if err := os.WriteFile(out, b.Bytes(), 0o644); err != nil {
		panic(err)
	}
}
