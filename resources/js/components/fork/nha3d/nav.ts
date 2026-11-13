// Đồ thị điểm đi lại (sàn hai tầng, cầu thang, vườn) + tìm đường A*.
import * as THREE from 'three';

export interface NavNode {
    id: string;
    p: THREE.Vector3;
    nb: Set<string>;
}

export class NavGraph {
    readonly nodes = new Map<string, NavNode>();

    add(id: string, x: number, y: number, z: number) {
        this.nodes.set(id, {
            id,
            p: new THREE.Vector3(x, y, z),
            nb: new Set(),
        });

        return id;
    }

    link(...ids: string[]) {
        for (let i = 0; i + 1 < ids.length; i++) {
            const a = this.nodes.get(ids[i]);
            const b = this.nodes.get(ids[i + 1]);
            if (!a || !b) {
                throw new Error(`nav: thiếu điểm ${ids[i]} / ${ids[i + 1]}`);
            }
            a.nb.add(b.id);
            b.nb.add(a.id);
        }
    }

    /** Nối mọi cặp trong nhóm (khoảng trống thoáng như bãi cỏ). */
    mesh(ids: string[], maxDist = 7) {
        for (let i = 0; i < ids.length; i++) {
            for (let j = i + 1; j < ids.length; j++) {
                if (this.pos(ids[i]).distanceTo(this.pos(ids[j])) <= maxDist) {
                    this.link(ids[i], ids[j]);
                }
            }
        }
    }

    pos(id: string): THREE.Vector3 {
        const n = this.nodes.get(id);
        if (!n) {
            throw new Error(`nav: không có điểm ${id}`);
        }

        return n.p;
    }

    has(id: string) {
        return this.nodes.has(id);
    }

    /** Điểm gần nhất (ưu tiên cùng tầng). */
    nearest(p: THREE.Vector3, filter?: (id: string) => boolean): string {
        let best = '';
        let bd = Infinity;
        for (const n of this.nodes.values()) {
            if (filter && !filter(n.id)) {
                continue;
            }
            const d = Math.hypot(n.p.x - p.x, (n.p.y - p.y) * 4, n.p.z - p.z);
            if (d < bd) {
                bd = d;
                best = n.id;
            }
        }

        return best;
    }

    /** A*: trả danh sách id từ `from` tới `to` (gồm cả hai đầu), rỗng nếu không tới được. */
    path(from: string, to: string): string[] {
        if (from === to) {
            return [from];
        }
        const goal = this.nodes.get(to);
        if (!goal || !this.nodes.has(from)) {
            return [];
        }
        const g = new Map<string, number>([[from, 0]]);
        const f = new Map<string, number>([
            [from, this.pos(from).distanceTo(goal.p)],
        ]);
        const came = new Map<string, string>();
        const open = new Set<string>([from]);
        while (open.size) {
            let cur = '';
            let bf = Infinity;
            for (const id of open) {
                const v = f.get(id) ?? Infinity;
                if (v < bf) {
                    bf = v;
                    cur = id;
                }
            }
            if (cur === to) {
                const out = [cur];
                while (came.has(out[0])) {
                    out.unshift(came.get(out[0])!);
                }

                return out;
            }
            open.delete(cur);
            const cn = this.nodes.get(cur)!;
            for (const nb of cn.nb) {
                const tg =
                    (g.get(cur) ?? Infinity) + cn.p.distanceTo(this.pos(nb));
                if (tg < (g.get(nb) ?? Infinity)) {
                    came.set(nb, cur);
                    g.set(nb, tg);
                    f.set(nb, tg + this.pos(nb).distanceTo(goal.p));
                    open.add(nb);
                }
            }
        }

        return [];
    }
}
