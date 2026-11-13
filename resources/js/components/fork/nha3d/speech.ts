// Người điều phối lời nói: mỗi nhân vật một bong bóng một lúc, nghỉ giữa hai câu một khoảng ngẫu nhiên
// (dài ngắn theo độ dài câu, đang mệt hay không), cả xưởng không nói chen quá dày khi chỉ là chuyện phiếm.
// Riêng lúc đối đáp thật (A nói, B đáp lại 1–2 giây sau, A vặn lại một câu) thì cho nói nhanh, xong cùng im một lúc.
import { rand } from './util';

/** work: việc thật (giao giấy, chấm điểm…) · reply: câu đáp trong một cuộc đối đáp · greet: chào sếp · chat: chuyện phiếm. */
export type Prio = 'work' | 'reply' | 'greet' | 'chat';

interface Who {
    at: number;
    text: string;
    quiet: number;
    burst: number[];
}

export class Speech {
    private who = new Map<string, Who>();
    private nextChat = 0;
    private nextGreet = 0;
    private recent = new Map<string, number>();
    /** Ai đang mệt (nghỉ lâu hơn giữa các câu). */
    tired: (who: string) => boolean = () => false;

    constructor(private now: () => number) {}

    /** Cho phép `who` nói `text` lúc này không? (có thì ghi nhận luôn) */
    allow(who: string, text: string, prio: Prio): boolean {
        const t = this.now();
        const w = this.who.get(who) ?? {
            at: -99,
            text: '',
            quiet: 0,
            burst: [],
        };
        if (w.text === text && t - w.at < 120) {
            return false; // không lặp lại đúng câu vừa nói
        }
        w.burst = w.burst.filter((x) => t - x < 14);
        if (prio !== 'work' && w.burst.length >= 3) {
            return false; // không bao giờ tuôn một tràng
        }
        const len = text.length;
        const slow = this.tired(who) ? 1.35 : 1;
        switch (prio) {
            case 'work':
                if (t - w.at < 1.8) {
                    return false;
                }
                w.quiet = t + rand(2.5, 5) + len * 0.03;
                break;
            case 'reply':
                if (t - w.at < 1.2) {
                    return false;
                }
                // đối đáp xong thì im một lúc
                w.quiet = t + (rand(7, 15) + len * 0.05) * slow;
                break;
            case 'greet':
                if (t < w.quiet || t < this.nextGreet) {
                    return false;
                }
                this.nextGreet = t + rand(0.9, 2.2);
                w.quiet = t + rand(6, 11) * slow;
                break;
            default: {
                if (t < w.quiet || t < this.nextChat) {
                    return false;
                }
                const r = this.recent.get(text);
                if (r !== undefined && t - r < 45) {
                    return false; // cả xưởng vừa có người nói y chang
                }
                this.nextChat = t + rand(2.2, 6.5);
                w.quiet = t + (rand(8, 18) + len * 0.06) * slow;
            }
        }
        w.at = t;
        w.text = text;
        w.burst.push(t);
        this.who.set(who, w);
        this.recent.set(text, t);
        if (this.recent.size > 80) {
            for (const [k, v] of this.recent) {
                if (t - v > 60) {
                    this.recent.delete(k);
                }
            }
        }

        return true;
    }

    /** Lưu nhịp nói (để quay lại trang không bị cả xưởng nói dồn một lúc). */
    snapshot() {
        return {
            who: [...this.who.entries()],
            nextChat: this.nextChat,
            nextGreet: this.nextGreet,
            recent: [...this.recent.entries()],
        };
    }

    restore(s: ReturnType<Speech['snapshot']>) {
        this.who = new Map(s.who);
        this.nextChat = s.nextChat;
        this.nextGreet = s.nextGreet;
        this.recent = new Map(s.recent);
    }

    /** Bong bóng hiện 3–5 giây tuỳ độ dài câu (có chút ngẫu nhiên cho tự nhiên). */
    static dur(text: string) {
        return Math.min(
            5,
            Math.max(3, 2.3 + text.length * 0.05 + rand(-0.3, 0.4)),
        );
    }
}
