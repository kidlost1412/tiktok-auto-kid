// Nguồn video: "AI" = video Xưởng Video làm (hub/kho/ra), "Kho riêng" = video anh tự bỏ vào thư mục riêng.
export type SourceKind = 'ai' | 'rieng';

/** Bộ lọc nguồn dùng chung (Tổng quan, Số liệu…). */
export type SourceFilter = 'all' | SourceKind;

export const sourceKind = (source: string | null | undefined): SourceKind | null => {
    if (!source) {
        return null;
    }

    return source === 'rieng' ? 'rieng' : 'ai';
};

export const SOURCE_LABEL: Record<SourceKind, string> = {
    ai: 'AI',
    rieng: 'Kho riêng',
};

export const SOURCE_TITLE: Record<SourceKind, string> = {
    ai: 'Video do Xưởng Video (AI) làm, đăng tự động',
    rieng: 'Video anh tự bỏ vào Kho riêng',
};

export const SOURCE_FILTERS: { value: SourceFilter; label: string }[] = [
    { value: 'all', label: 'Tất cả' },
    { value: 'ai', label: 'Video AI' },
    { value: 'rieng', label: 'Kho riêng' },
];

export const matchesSource = (source: string | null | undefined, filter: SourceFilter): boolean =>
    filter === 'all' || sourceKind(source) === filter;
