// Mỗi kênh một màu trên Lịch đăng (vạch màu đầu dòng, chip @kênh, nút lọc). Màu cố định theo thứ tự kênh trong danh sách.
// Tránh các màu đã dùng cho trạng thái (xanh dương = TikTok, xanh lá = đã đăng, đỏ = lỗi, vàng = cảnh báo, tím = đăng thẳng).
export interface ChannelColor {
    /** Chấm tròn / vạch màu. */
    dot: string;
    /** Chip @kênh (nền nhạt + chữ). */
    chip: string;
}

const PALETTE: ChannelColor[] = [
    {
        dot: 'bg-pink-500',
        chip: 'bg-pink-500/10 text-pink-700 dark:text-pink-300',
    },
    {
        dot: 'bg-teal-500',
        chip: 'bg-teal-500/10 text-teal-700 dark:text-teal-300',
    },
    {
        dot: 'bg-orange-500',
        chip: 'bg-orange-500/10 text-orange-700 dark:text-orange-300',
    },
    {
        dot: 'bg-indigo-500',
        chip: 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-300',
    },
    {
        dot: 'bg-lime-500',
        chip: 'bg-lime-500/15 text-lime-800 dark:text-lime-300',
    },
    {
        dot: 'bg-fuchsia-500',
        chip: 'bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300',
    },
    {
        dot: 'bg-cyan-600',
        chip: 'bg-cyan-500/10 text-cyan-800 dark:text-cyan-300',
    },
    {
        dot: 'bg-stone-500',
        chip: 'bg-stone-500/15 text-stone-700 dark:text-stone-300',
    },
];

export const channelColor = (index: number | undefined): ChannelColor =>
    PALETTE[(index ?? 0) % PALETTE.length];
