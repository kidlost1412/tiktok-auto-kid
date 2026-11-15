// Tên kênh TikTok: chỗ thì server đã gắn sẵn "@", chỗ thì chưa. Luôn ra đúng một dấu "@".
export function atHandle(value: string | null | undefined): string {
    const name = (value ?? '').trim().replace(/^@+/, '');

    return name === '' ? '' : `@${name}`;
}
