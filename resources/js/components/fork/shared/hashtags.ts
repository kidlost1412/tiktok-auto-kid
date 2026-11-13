// Hashtag dùng chung cho giao diện: tách chuỗi nhập thành danh sách hashtag hợp lệ (cùng quy tắc với máy chủ).

export interface TagSuggestion {
    tag: string;
    uses: number;
}

/** Cùng quy tắc với máy chủ (Hashtags::normalize): chữ, số, gạch dưới; bỏ trùng không phân biệt hoa thường. */
export function parseTags(raw: string, max = 50): string[] {
    const out: string[] = [];
    const seen = new Set<string>();

    for (const part of raw.split(/[\s,;]+/)) {
        const word = part.replace(/^#+/, '').replace(/[^\p{L}\p{N}_]+/gu, '');
        const key = word.toLowerCase();

        if (!word || word.length > 99 || seen.has(key)) {
            continue;
        }

        seen.add(key);
        out.push(`#${word}`);

        if (out.length >= max) {
            break;
        }
    }

    return out;
}
