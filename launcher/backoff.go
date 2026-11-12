package main

import "time"

// Backoff tăng gấp đôi thời gian chờ từ Min đến Max.
type Backoff struct {
	Min, Max time.Duration
	cur      time.Duration
}

func NewBackoff(min, max time.Duration) *Backoff { return &Backoff{Min: min, Max: max} }

// Next trả về thời gian chờ kế tiếp.
func (b *Backoff) Next() time.Duration {
	if b.cur == 0 {
		b.cur = b.Min
	} else {
		b.cur *= 2
		if b.cur > b.Max {
			b.cur = b.Max
		}
	}
	return b.cur
}

// Reset đưa về thời gian chờ nhỏ nhất.
func (b *Backoff) Reset() { b.cur = 0 }
