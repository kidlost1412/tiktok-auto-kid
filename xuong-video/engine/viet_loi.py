"""Viết lời + phương án dựng bằng Claude CLI headless (mỗi lần gọi là phiên MỚI, không lịch sử chat).
viet(ma_sp, so_ban) -> list kịch bản đã qua kiểm.
Mỗi kịch bản được giao một tổ hợp 5 trục xoay vòng: góc bán · MO (kiểu câu mở) · THAN (kiểu thân bài) · CHOT (kiểu chốt) · VAI (người nói)."""
import json, os, random, re
from collections import Counter
from pathlib import Path


import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, khung_giay, khung_am_tiet, glob_kem
CFG = cfg_hub()
from ai import goi, lay_json, HetHanMuc  # noqa: E402
import su_kien as SK  # noqa: E402  (tự thoại của Biên kịch ở Khu Tự Trị: chỉ ghi sự kiện, nuốt mọi lỗi)
import truc_tiep as TT  # noqa: E402  (việc trực tiếp của Biên kịch: ekip mở sẵn, viet() chỉ cập nhật bước + dòng thật)
import prompt_mau  # noqa: E402

MIN_VIDEO_SO_LIEU, MIN_TRUNG_VI = 15, 200       # số liệu TikTok chỉ gửi/dùng khi nhóm ≥ 15 video và trung vị ≥ 200 view/24h (nhỏ hơn là nhiễu)


# ---------------------------------------------------------------- số liệu TikTok (chỉ khi đủ tin cậy)
def _cong_so_lieu(ma):
    """True khi nhóm số liệu (của sản phẩm nếu đủ video, không thì của mọi sản phẩm — giống hieu_qua.tom_tat) có ≥ 15 video và trung vị ≥ 200 view/24h.
    Đọc thẳng lich-su/hieu-qua.json (hieu_qua không công khai kích thước nhóm)."""
    try:
        c = CFG.get("hieu_qua") or {}
        if not c.get("bat", True):
            return False
        db = json.loads((HUB / "lich-su" / "hieu-qua.json").read_text(encoding="utf-8"))
        diem = lambda r: r.get("xem24") if r.get("xem24") is not None else r.get("xem72")
        tat_ca = [r for r in db.values() if isinstance(r, dict) and isinstance(diem(r), (int, float))]
        rieng = [r for r in tat_ca if r.get("ma") == ma]
        nguon = rieng if len(rieng) >= int(c.get("mau_tong", 6)) else tat_ca
        if len(nguon) < MIN_VIDEO_SO_LIEU:
            return False
        v = sorted(diem(r) for r in nguon)
        trung_vi = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
        return trung_vi >= MIN_TRUNG_VI
    except Exception:
        return False


def _he_so(ma, chieu):
    """Hệ số xoay vòng theo hiệu quả thật — chỉ khi số liệu đủ tin cậy (cổng _cong_so_lieu), không thì {} (xoay đều)."""
    try:
        if not _cong_so_lieu(ma):
            return {}
        from hieu_qua import he_so
        return he_so(ma, chieu)
    except Exception:
        return {}


def _tom_tat(ma, cho="bien_kich"):
    try:
        from hieu_qua import tom_tat
        return tom_tat(ma, cho)
    except Exception:
        return ""


def _so_lieu(ma):
    """Đoạn số liệu TikTok gửi biên kịch: "" nếu nhóm chưa đủ video / view quá nhỏ."""
    return _tom_tat(ma) if _cong_so_lieu(ma) else ""


CAM_CHU = ["số 1", "số một", "nhất thị trường", "duy nhất", "chết"]    # chủ quyết định: nội dung TikTok không giới hạn, chỉ cấm các tuyên bố này; 23/11 Kid: không bao giờ "chết"
_THAY_CHET = [(r"cây\s+chết", "cây lụi"), (r"chết\s+cây", "lụi cây"), (r"chết\s+sạch", "sạch bóng"), (r"chết", "gục")]


def bo_chet(t):
    """23/11 Kid: không bao giờ dùng từ "chết" trong video → thay từ cùng nghĩa (giữ HOA nếu chữ gốc viết hoa)."""
    t = str(t or "")
    for a, b in _THAY_CHET:
        t = re.sub(r"(?<!\w)" + a + r"(?!\w)", lambda m, b=b: b.upper() if m.group(0).isupper() else (b[:1].upper() + b[1:] if m.group(0)[:1].isupper() else b), t, flags=re.I)
    return t
VAN_MAU_YEU = ["tham khảo", "xem chi tiết", "tìm hiểu thêm", "đáng cân nhắc", "theo hướng dẫn của", "quy cách rõ ràng",
               "đúng nhu cầu", "giải pháp toàn diện", "hiệu quả vượt trội", "chất lượng hàng đầu"]
BANNED = CAM_CHU + VAN_MAU_YEU


def history_sentences(limit=400):
    f = HUB / "lich-su" / "cau-da-dung.txt"
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]


def cau_cua_sp(ma, limit=150):
    """Câu đã dùng của RIÊNG sản phẩm này (máy chống trùng). Chưa có sổ riêng → dựng từ hồ sơ các video đã làm của sản phẩm."""
    f = HUB / "lich-su" / f"cau-da-dung-{ma}.txt"
    if not f.exists():
        ds = []
        for j in glob_kem(Path(CFG["duong_dan"]["ra"]), f"{ma}_*.json"):
            try:
                t = (json.loads(j.read_text(encoding="utf-8")).get("kich_ban") or {}).get("text") or ""
            except Exception:
                continue
            ds += [x.strip() for x in re.split(r"(?<=[.!?])\s+", re.sub(r"\[[^\]]*\]", "", t).strip()) if x.strip()]
        ds = list(dict.fromkeys(ds))
        if ds:
            f.write_text("".join(x + "\n" for x in ds), encoding="utf-8")
        return ds[-limit:]
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]


def recent_styles(limit=20):
    f = HUB / "lich-su" / "phong-cach.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()[-limit:] if l.strip()]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", s.lower())).strip()


# ---------------------------------------------------------------- BỐN TRỤC (mỗi kịch bản một tổ hợp)
MO = {   # kiểu câu mở (hook) = MỘT đòn tâm lý khách: khoá → (mô tả gửi biên kịch, ví dụ chỉ để thấy độ mạnh — KHÔNG chép, KHÔNG làm khuôn).
         # Hook là hook BÁN HÀNG: cụ thể (con số thật, việc thật, cái mất thấy được), dứt khoát (phán thẳng, không rào đón), nghe một lần là hiểu.
         # KHÔNG kể chuyện, KHÔNG đóng vai, KHÔNG dựng nhân vật. Kiểu nào cũng được, miễn hook HAY; nội dung đa dạng là quan trọng nhất.
    # — tò mò: điều người nghe chưa biết
    'bi_mat_nghe': ('Bí mật người trong nghề: một điều có giá mà ít ai nói ra; người nghe phải nghe hết mới biết.', 'Đại lý phân bón ít khi nói cho bà con biết cái này: cây chỉ ăn được phần nhỏ trong bao phân.'),
    'vach_tran': ('Vạch trần: một điều người bán, đại lý hay thói quen cũ không nói thật với nhà vườn; câu sau nói thẳng sự thật (đúng KIẾN THỨC sản phẩm).', 'Đạm cá mở nắp ra không nghe mùi cá mà nghe mùi phân hoá học, thì vứt.'),
    'su_that_bat_ngo': ('Một sự thật bất ngờ lấy từ KIẾN THỨC thực tế của sản phẩm (cơ chế, cách dùng) mà nhà vườn lâu năm cũng chưa biết.', 'Rải phân urê xuống gốc, cây hút được chừng ba phần mười, còn lại trôi mất.'),
    'cau_do': ('Câu đố cho người nghe tự đoán, đáp án bất ngờ (đáp án là sự thật trong hồ sơ).', 'Một can năm lít pha được bao nhiêu bình mười sáu lít? Đoán thử coi.'),
    'con_so': ('Một con số THẬT trong hồ sơ (liều, tiền, phần trăm), đặt cạnh một con số khác cho thấy chênh lệch.', 'Tám trăm nghìn một bao phân mà cây chỉ ăn được chưa tới phân nửa.'),
    # — sợ mất: tiền, công, mùa
    'mat_tien': ('Tiền, công, phân thuốc đang bị phí — nói bằng con số, phần trăm, số lần phun cụ thể, không nói chung chung.', 'Bón mười phần phân mà cây ăn chưa tới bốn phần, sáu phần còn lại là tiền bỏ đất.'),
    'mat_mat': ('Một sai nhỏ ai cũng làm, mà hậu quả lớn, nói rõ hậu quả gì.', 'Pha đồng chung thuốc mà đổ thuốc vô trước, cả bình kết tủa, đem đổ bỏ.'),
    'dung_tay': ('Bảo người nghe KHOAN làm việc họ sắp làm, nói rõ vì sao.', 'Khoan rải thêm phân, đất chai thì rải bao nhiêu cây cũng không ăn được.'),
    'hang_xom': ('So với nhà bên: cùng làm như nhau mà người ta được hơn mình — nói rõ hơn ở chỗ nào.', 'Cùng phun đồng, nhà bên một lần phun mà sạch, nhà mình phun hai lần vẫn còn rêu.'),
    # — lật lại điều ai cũng tin, phán thẳng
    'nghich_ly': ('Một câu nghe vô lý mà đúng, khiến người ta khựng lại; thân bài phải giải thích được.', 'Bón phân càng nhiều, đất càng chai, cây càng đói.'),
    'pha_niem_tin': ('Phủ nhận thẳng một điều nhà nông tin lâu nay.', 'Ai nói phun đồng là phải cháy đọt? Đó là do loại đồng, không phải do đồng.'),
    'phan_quyet': ('Phán một câu dứt khoát như người rành hàng: loại nào bỏ, loại nào giữ, dấu hiệu nào là hàng dỏm.', 'Phun đồng xong mà lá còn vệt trắng, loại đồng đó bỏ được rồi.'),
    'go_ngai': ('Nói thẳng nỗi ngại lớn nhất khi mua món này, rồi lật nó bằng một sự thật trong hồ sơ.', 'Sợ phun đồng cháy đọt? Chín phần mười bà con chưa biết tới loại đồng này.'),
    'so_sanh': ('Đặt hai thứ cạnh nhau (cách cũ và cách này, loại thường và loại này) bằng con số hay hình ảnh thấy được, đúng hồ sơ; không nêu tên hãng khác.', 'Một lần phun chai này bằng hai lần phun đồng thường.'),
    'nguoc_tam_ly': ('Nói ngược kiểu "đừng mua nếu…" để người nghe tự xét mình có thuộc nhóm cần không.', 'Vườn đang đậu trái đều thì đừng mua can này.'),
    'noi_thiet': ('Nói thiệt một câu hơi ngược chuyện bán hàng, nên nghe đáng tin; vẫn là ý bán hàng, không kể chuyện.', 'Nói thiệt, đợi vườn bệnh rồi mới mua thì em bán được nhiều hơn.'),
    'ket_qua_truoc': ('Đưa kết quả thấy được ra trước, nói chắc như người đã thấy tận mắt (đúng công dụng trong hồ sơ), rồi mới nói làm gì.', 'Thân mai đầy rêu xanh, phun một đợt là rêu sạch trơn, khỏi lo lây lan.'),
    'giai_oan': ('Gỡ cảm giác có lỗi: lỗi không nằm ở người trồng, mà ở một nguyên nhân họ không thấy; nói rõ nguyên nhân.', 'Cây không lớn đâu phải tại bón ít, mà tại cây không hút nổi phân đã bón.'),
    # — đúng người, đúng lúc, được lợi
    'goi_dung_nguoi': ('Gọi đúng nhóm người kèm đúng cái họ đang mất hoặc đang muốn, cụ thể tới mức người đó thấy là nói mình.', 'Trồng tiêu mà năm nào cũng phun đồng ba bốn đợt, nghe cái này đỡ được một nửa.'),
    'dung_luc': ('Một mốc mùa vụ thật đang tới gần, lỡ là mất gì — nói rõ cái mất.', 'Còn hơn tháng nữa là Tết, thân mai còn rêu là khách lắc đầu.'),
    'rao_viral': ('Lời rao viral kiểu dân bán hàng: nói lớn về độ phủ, độ tin dùng để kéo người nghe (không dùng chữ cấm như "số 1", "nhất", "duy nhất").',
                  'Sáu mươi ba tỉnh, hết sáu mươi hai tỉnh xài can này rồi!'),
    'qua_truoc': ('Mở thẳng bằng món quà có thật trong hồ sơ, nói sao cho thấy lời.', 'Lấy năm chai mà về tới nhà thành sáu, kèm thêm hai món.'),
    'het_rui_ro': ('Gỡ rủi ro khi mua bằng điều có thật trong hồ sơ (nhận hàng rồi mới trả tiền, trả hàng miễn phí, lấy ít thử trước).', 'Nhận hàng, mở ra coi đúng hàng rồi mới trả tiền, không ưng thì trả.'),
    'chu_tren_nhan': ('Lấy một chữ, một con số THẬT trên nhãn (thành phần, số giấy phép, hàm lượng) làm bằng chứng, nói như người rành hàng chỉ cho khách.', 'Lật mặt sau can đạm cá, chữ "chất hữu cơ hai mươi phần trăm" là thứ phải tìm.'),
    'thach_nhin': ('Thách người nghe tự kiểm tra một điều ngay ở vườn hay ở chai phân nhà mình, có kết luận rõ.', 'Mở nắp can đạm cá nhà mình ra ngửi thử, không có mùi cá là hàng pha.'),
}
_MO_VUON = {"thach_nhin"}     # hook bắt ra vườn coi: dùng ít
THAN = {   # kiểu thân bài (cũng là DANG_BAI: trường `dang` của kịch bản = khoá THAN, thống kê cũ còn chạy)
    'van_de_giai_phap': 'Vấn đề → một câu khoét hậu quả nếu để yên → sản phẩm vào → dùng thế nào.',
    'ba_sai_lam': 'Ba cái sai hay gặp, cái thứ ba dẫn thẳng tới sản phẩm.',
    'so_sanh': 'Đặt cách cũ / loại thường cạnh món này bằng con số hay cái thấy được (đúng hồ sơ, không nêu tên hãng) → vì sao khác → dùng sao.',
    'go_ngai': 'Hai nỗi ngại thật khi mua món này (sợ cháy, sợ dỏm, sợ phí…) → trả lời thẳng từng cái bằng sự thật trong hồ sơ.',
    'phep_tinh': 'Một phép tính tiện/đỡ công bằng con số thật (một chai pha bao nhiêu, phun được bao nhiêu, tính ra mỗi bình bao nhiêu tiền nếu hồ sơ có giá).',
    'tung_buoc': 'Hai hoặc ba bước làm, bước nào cũng thấy được bằng hình.',
    'khach_hoi': 'Một câu bà con hay hỏi về món này → trả lời gọn, chắc, như người rành hàng (không dựng chuyện người hỏi).',
    'dau_hieu': 'Hai ba dấu hiệu nhìn thấy ngoài vườn → cùng một chai xử lý.',
    'vi_sao': 'Giải thích MỘT cơ chế (vì sao nó làm được) lấy từ KIẾN THỨC thực tế của sản phẩm, bằng một ví von đời thường dễ hình dung.',
}
DANG_BAI = THAN
CHOT = {   # kiểu câu chốt (bài nào cũng nhắc giỏ hàng MỘT lần, nói ngắn; quà chỉ nhắc khi kiểu chốt yêu cầu)
    'qua_cu_the': 'Giỏ hàng + đúng MỘT mức quà trong hồ sơ.',
    'thu_it': 'Giảm rủi ro: gợi ý lấy ít để thử trên một phần vườn trước.',
    'kip_luc': 'Nhắc thời điểm: làm trước khi mưa/đợt đọt/mùa bệnh tới.',
    'hoi_nguoc': 'Kết bằng một câu hỏi ngắn để người xem tự trả lời, rồi chỉ giỏ hàng.',
    'chot_nhe': 'Nói như người quen: chai nằm sẵn ở giỏ hàng, cần thì lấy.',
    'phep_tinh_chot': 'Nhắc lại con số tiện nhất rồi chỉ giỏ hàng.',
    'dong_hanh': 'Bên em gửi hàng từ kho, có gì cứ nhắn — rồi chỉ giỏ hàng (chỉ dùng khi hồ sơ cho phép nói "bên em").',
}
VAI = {   # người nói: một giọng đọc (không dùng tag nhập vai): người làm nội dung bán hàng
    'nguoi_noi_dung': ('Người làm nội dung bán hàng viral, am hiểu nông nghiệp và hiểu sản phẩm tới nơi (làm được gì, vì sao, dùng sao cho đúng), '
                       'nói với nhà nông chân chất, mộc mạc. Xưng "em"; gọi "các bác" hoặc "bà con" ở chỗ tự nhiên. Nói thẳng vào cái lợi, '
                       'không kể chuyện, không dựng nhân vật; điều nói về sản phẩm phải đúng hồ sơ và kiến thức sản phẩm.'),
}
LUAT_CAU_MO = ('5 giây đầu là tất cả: hook bán hàng mạnh, dứt khoát, đúng đòn tâm lý được giao, khiến người đang lướt phải dừng lại nghe tiếp; '
               'sức hút nằm ở Ý của hook: cụ thể (con số thật, việc thật, cái mất thấy được), phán thẳng; không mơ hồ, không kể chuyện; KHÔNG nằm ở tiếng gọi hay dấu "!"; '
               'câu đầu vào thẳng ý hook, KHÔNG mở bằng tiếng gọi ("Các bác ơi", "Bà con ơi") hay lời chào, '
               'không mở bằng tên sản phẩm (trừ kiểu qua_truoc, con_so, rao_viral); câu thứ hai trả ngay một phần chỗ hở, không vòng vo.')
_VAI_HOP = {}   # ràng buộc tổ hợp: khoá (mo | than | chot) → các vai được phép (chỉ còn một giọng nên trống)
TRUC = {"mo": MO, "than": THAN, "chot": CHOT, "vai": VAI}
_CHIEU_HIEU_QUA = {"goc": "goc", "mo": "mo", "than": "dang", "chot": "chot", "vai": "vai"}


def dem_lich_su(ten, n=200):
    f = HUB / "lich-su" / ten
    try:
        return f.read_text(encoding="utf-8").splitlines()[-n:] if f.exists() else []
    except Exception:
        return []


def _them_so(ten, dong):
    """Ghi thêm 1 dòng vào sổ lịch sử. Lỗi ghi file không bao giờ làm hỏng dây chuyền."""
    try:
        from su_kien import noi_them       # ghi nối có khoá file (sổ riêng từng sản phẩm, nhưng nhất quán với các sổ khác)
        noi_them(HUB / "lich-su" / ten, str(dong).replace("\n", " ") + "\n")
    except Exception:
        pass


def _chon(khoa, dem, hs=None, rng=random, ok=None):
    """Chọn 1 khoá: ÍT DÙNG NHẤT trước (đếm chia hệ số hiệu quả 0.7–1.5 nếu có), cùng mức thì ngẫu nhiên (rng=None → theo thứ tự khai báo).
    ok(khoá) lọc ràng buộc; không khoá nào thoả thì bỏ ràng buộc."""
    hs = hs or {}
    ds = [k for k in khoa if ok is None or ok(k)] or list(khoa)
    return min(ds, key=lambda k: (dem.get(k, 0) / (hs.get(k) or 1.0), rng.random() if rng else 0))


def _co_ben_em(sp):
    return "bên em" in json.dumps(sp.get("su_that_duoc_noi") or [], ensure_ascii=False).lower()


def _vai_cho_phep(mo, than, chot):
    ok = set(VAI)
    for k in (mo, than, chot):
        if k in _VAI_HOP:
            ok &= _VAI_HOP[k]
    return ok


def moi_dem(ma=None):
    """Số lần đã dùng từng khoá của mỗi trục (từ sổ lịch sử của sản phẩm; ma=None → trống)."""
    ten = {"goc": "goc", "mo": "mo", "than": "than", "chot": "chot", "vai": "vai"}
    return {ax: Counter(dem_lich_su(f"{t}-{ma}.txt") if ma else []) for ax, t in ten.items()}


def lo_moi():
    return {"mo": set(), "qua": 0, "dan": 0, "vuon": 0}


def gan_truc(sp, goc, need, dem, hs=None, lo=None, tong=None, rng=random):
    """Giao cho `need` kịch bản mỗi bản một tổ hợp {goc, mo, than, chot, vai}.
    - mỗi trục xoay vòng: ít dùng nhất trước, có ngẫu nhiên, nhân hệ số hiệu quả `hs[trục]` nếu có (dem, lo được cập nhật tại chỗ);
    - trong MỘT lô (`lo`) không lặp mo cho tới khi dùng hết các kiểu; hook kể chuyện vườn (_MO_VUON) tối đa 1/10 số bản; không quá 1/4 số bản (`tong`) chốt qua_cu_the (trừ góc qua-tang); 
    - ràng buộc tổ hợp: qua_truoc ⇒ chot qua_cu_the; 
      dong_hanh cần hồ sơ có "bên em". Vi phạm → bốc lại trục đó (chỉ bốc trong các khoá hợp lệ)."""
    hs, lo = hs or {}, lo if lo is not None else lo_moi()
    tong = max(tong or need, 1)
    gioi_qua, gioi_vuon = max(1, tong // 4), max(1, tong // 10)
    ben_em = _co_ben_em(sp)
    co_qua = bool(sp.get("qua_tang"))
    if not co_qua:                                          # không có quà thì không giao góc quà tặng (hết góc khác mới đành giữ)
        goc = [x for x in goc if x != "qua-tang"] or goc
    out = []
    for _ in range(need):
        g = _chon(goc, dem["goc"], hs.get("goc"), rng)
        qua_ok = g == "qua-tang" or lo["qua"] < gioi_qua
        if all(k in lo["mo"] or (k in _MO_VUON and lo.get("vuon", 0) >= gioi_vuon) for k in MO):
            lo["mo"].clear()
        mo = _chon(list(MO), dem["mo"], hs.get("mo"), rng, lambda k: k not in lo["mo"] and (k != "qua_truoc" or qua_ok)
                   and (k not in _MO_VUON or lo.get("vuon", 0) < gioi_vuon))
        than = _chon(list(THAN), dem["than"], hs.get("than"), rng)
        chot = "qua_cu_the" if mo == "qua_truoc" else _chon(list(CHOT), dem["chot"], hs.get("chot"), rng,
                                                              lambda k: (k != "qua_cu_the" or qua_ok) and (k != "dong_hanh" or ben_em))
        if g == "qua-tang" and co_qua:                      # góc quà tặng có quà thật → chốt bằng quà cụ thể (không tính hạn mức 1/4)
            chot = "qua_cu_the"
        cho = _vai_cho_phep(mo, than, chot)
        vai = _chon(list(VAI), dem["vai"], hs.get("vai"), rng, lambda k: k in cho)
        lo["mo"].add(mo)
        if mo in _MO_VUON:
            lo["vuon"] = lo.get("vuon", 0) + 1
        if chot == "qua_cu_the" and g != "qua-tang":
            lo["qua"] += 1
        for ax, k in (("goc", g), ("mo", mo), ("than", than), ("chot", chot), ("vai", vai)):
            dem[ax][k] += 1
        out.append({"goc": g, "mo": mo, "than": than, "chot": chot, "vai": vai})
    return out


# ---------------------------------------------------------------- khối dữ liệu tuỳ chọn cho đề bài
def _mo_ta_goc(g):
    """Mô tả một góc bán trong hồ sơ (các trường chữ ngoài `ma`, nối lại)."""
    return " ".join(str(v).strip() for k, v in g.items() if k != "ma" and isinstance(v, str) and v.strip())


def _de_bai(sp, truc):
    """Mỗi bản một khối: góc + kiểu mở/thân/chốt + vai (chỉ gửi mô tả của khoá được giao; góc lấy mô tả trong goc_ban của hồ sơ)."""
    gm = {g["ma"]: _mo_ta_goc(g) for g in sp.get("goc_ban") or [] if isinstance(g, dict) and g.get("ma")}
    dong, co_mo = [], False
    vai_dung = list(dict.fromkeys(t["vai"] for t in truc if t.get("vai") in VAI))
    if vai_dung:                                      # mô tả vai in MỘT lần ở đầu, mỗi bản chỉ ghi tên vai
        dong.append("Vai được giao (mô tả chung, mỗi bản ghi tên vai):")
        dong += [f"   {k} — {VAI[k]}" for k in vai_dung]
    for i, t in enumerate(truc):
        g = t.get("goc") or ""
        dong.append(f"bai[{i}]: góc = {g}" + (f" ({gm[g]})" if gm.get(g) else ""))
        if t.get("mo") in MO:
            co_mo = True
            dong.append(f'   kiểu mở = {t["mo"]} — {MO[t["mo"]][0]} (ví dụ cấu trúc, KHÔNG chép: "{MO[t["mo"]][1]}")')
        for ax, ten in (("than", "kiểu thân"), ("chot", "kiểu chốt"), ("vai", "vai")):
            k = t.get(ax)
            if k in TRUC[ax]:
                dong.append(f"   {ten} = {k}" + ("" if ax == "vai" else f" — {TRUC[ax][k]}"))
    if co_mo:
        dong.append("Luật câu mở: " + LUAT_CAU_MO)
    return "\n".join(dong)


def _dd(p):
    """Đường dẫn dài trên Windows (> 260 ký tự): thêm tiền tố \\\\?\\."""
    s = str(p)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + os.path.abspath(s)


_GIONG_CACHE = {}


def _loi_hay_kho(kho):
    """Mọi `loi_hay` trong mô tả kiểu 2 (kieu == 2) của thư mục kho: <kho>/_mo-ta/**/*.mo-ta.json (bỏ thư mục con bắt đầu bằng _).
    Nhớ theo (thư mục kho, giờ sửa mới nhất) trong cả tiến trình."""
    try:
        if not kho:
            return []
        goc = _dd(Path(str(kho)) / "_mo-ta")
        if not os.path.isdir(goc):
            return []
        ds, mt = [], 0
        for d, con, files in os.walk(goc):
            con[:] = [x for x in con if not x.startswith("_")]
            for f in files:
                if f.endswith(".mo-ta.json"):
                    p = os.path.join(d, f); ds.append(p)
                    try:
                        mt = max(mt, os.stat(p).st_mtime_ns)
                    except OSError:
                        pass
        khoa = (str(kho), mt, len(ds))
        c = _GIONG_CACHE.get(str(kho))
        if c and c[0] == khoa:
            return c[1]
        out = []
        for p in sorted(ds):
            try:
                with open(p, encoding="utf-8-sig") as fh:
                    d = json.load(fh)
            except Exception:
                continue
            if isinstance(d, dict) and d.get("kieu") == 2:
                out += [s.strip() for s in (d.get("loi_hay") or []) if isinstance(s, str) and s.strip()] if isinstance(d.get("loi_hay"), list) else []
        _GIONG_CACHE[str(kho)] = (khoa, out)
        return out
    except Exception:
        return []


def _ten_sp_khac(sp):
    """Tên các sản phẩm KHÁC trong hub (câu thoại nhắc tên đó thì bỏ)."""
    ma, own = sp.get("ma"), [_chuan(x) for x in ten_phai_nhac(sp)]
    out = []
    try:
        for f in sorted((HUB / "san-pham").glob("*/san-pham.json")):
            if f.parent.name == ma:
                continue
            try:
                o = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if _la_kho_chung(o):
                continue
            for x in [o.get("ten_ngan"), o.get("ten_goi")] + list(o.get("ten_khac") or []):
                if isinstance(x, str) and len(x.strip()) >= 4:
                    c = _chuan(x)
                    if c not in out and not any(c in m for m in own):    # tên con của chính sản phẩm này thì không phân biệt được
                        out.append(c)
    except Exception:
        pass
    return out


def _la_kho_chung(o):
    return bool(o) and (o.get("loai") == "kho-chung" or bool(o.get("chi_la_kho_canh")))


def giong_that(sp, rng=None, toi_da=8):
    """Khối "GIỌNG NÓI THẬT NGOÀI VƯỜN": tối đa 8 `loi_hay` từ mô tả kiểu 2 của CHÍNH kho sản phẩm (không mượn kho khác),
    ưu tiên câu 8–30 từ, bỏ câu có chữ số và câu nhắc tên sản phẩm khác; cùng dữ liệu → cùng kết quả (xếp theo câu chuẩn hoá,
    `rng` giữ cho khỏi vỡ chỗ gọi cũ, không dùng). Không có → ""."""
    try:
        khac = _ten_sp_khac(sp)
        thay, ds = set(), []
        for c in _loi_hay_kho(sp.get("kho_video")):
            n = norm(c)
            if n and n not in thay and not re.search(r"\d", c) and not any(x in _chuan(c) for x in khac):
                thay.add(n); ds.append(c)
        vua = sorted((c for c in ds if 8 <= len(c.split()) <= 30), key=norm)
        con = sorted((c for c in ds if not 8 <= len(c.split()) <= 30), key=norm)
        chon = (vua + con)[:toi_da]
        if not chon:
            return ""
        return ("\n=== GIỌNG NÓI THẬT NGOÀI VƯỜN (người thật nói trong clip — học NHỊP và CÁCH DÙNG TỪ; không chép câu, không lấy số liệu hay công dụng từ đây) ===\n"
                + "\n".join(f'- "{c}"' for c in chon) + "\n")
    except Exception:
        return ""


_NHAN_VAI_TRO = [("chai_ro", "chai rõ nhãn"), ("nhan_can", "mặt sau nhãn"), ("pha_rot", "pha, rót"), ("phun", "phun, tưới"), ("re", "rễ, gốc"),
                 ("cay_con", "cây con"), ("van_de", "cây bệnh"), ("ket_qua", "cây khoẻ, kết quả"), ("vuon", "toàn cảnh vườn"), ("kho_hang", "kho hàng")]
_TEN_CAY = {"ca_phe": "cà phê", "ho_tieu": "hồ tiêu", "sau_rieng": "sầu riêng", "ot": "ớt", "rau_mau": "rau màu", "thanh_long": "thanh long"}


def _canh_bad(s):
    """Cảnh KHÔNG dùng (cùng luật soat_kho.bad): chữ chèn nhiều, hàng khác, quá xấu."""
    x = s.get("soat") or {}
    chu = x.get("chu_muc", 2 if x.get("chu") else 0)
    return bool(s.get("cam") or chu >= 2 or x.get("hang_khac") or (x.get("dep") or 3) <= 1)


CAY_DU = 30          # Kid 24/11: kho đạm cá có 17 cảnh sầu riêng (2 video gốc) mà biên kịch vẫn viết bài sầu riêng → hình toàn cà phê


def kho_canh(ma):
    """Khối "KHO CẢNH ĐANG CÓ" từ san-pham/<ma>/canh.json: số cảnh dùng được (không bad) theo vai trò, số cảnh người nói, cây trồng có trong kho. Chưa có → ""."""
    try:
        shots = json.loads((HUB / "san-pham" / ma / "canh.json").read_text(encoding="utf-8"))
        if not isinstance(shots, list):
            return ""
        ok = [s for s in shots if isinstance(s, dict) and not _canh_bad(s)]
        dem, cay, goc = Counter(), Counter(), {}
        for s in ok:
            for v in s.get("vai_tro") or []:
                dem[v] += 1
            for c in s.get("cay") or []:
                if c in _TEN_CAY:
                    cay[c] += 1; goc.setdefault(c, set()).add(str(s.get("file", "")))
        so = lambda n: f"{n}" + (" (ít)" if 0 < n <= 2 else "")
        noi = sum(1 for s in ok if ((s.get("soat") or {}).get("mat") or 0) >= 2)
        dong = " · ".join([f"{ten}: {so(dem[k])}" for k, ten in _NHAN_VAI_TRO] + [f"người nói: {so(noi)}"])
        return ("\n=== KHO CẢNH ĐANG CÓ (viết sao cho hình có thật; loại ghi 0 hoặc \"ít\" thì đừng viết câu cần đúng hình đó) ===\n" + dong + "\n"
                + (("Cây có trong kho (số cảnh / số video gốc): " + ", ".join(f"{_TEN_CAY[c]} {n}/{len(goc[c])}" for c, n in cay.most_common()) + ".\n"
                    f"Chỉ viết câu nói RIÊNG một cây (rễ sầu riêng, đọt cà phê…) khi cây đó có ≥ {CAY_DU} cảnh từ ≥ 3 video gốc; cây ít hơn thì nói chung"
                    " (\"cây\", \"vườn\", \"các loại cây\") để hình được đa dạng nhiều loại cây.\n") if cay else ""))
    except Exception:
        return ""


# ---------------------------------------------------------------- đề bài
# Bài học giám khảo nghiêng về cảnh/dựng; biên kịch chỉ cần dòng dính tới lời, chữ, quà, chốt
_RE_BAI_HOC_LOI = re.compile(r"lời|câu|nói|nhắc|viết|ghi\b|chốt|quà|giá|liều|tên", re.I)


# Việc của người dựng (chữ trên hình, bố cục, cắt cảnh, cảnh quay…): biên kịch không làm được, bỏ trước khi lọc theo từ "lời"
_RE_VIEC_DUNG = re.compile(r"khối chữ|chữ to|phụ đề|bố cục|cảnh đứng yên|đổi cảnh|cắt cảnh|hình cuối|cảnh chai|cảnh quà|nút giỏ|vùng 12%|che nhãn|đè nhãn|khung(?!\w)", re.I)


# Khoá hồ sơ chỉ máy dùng (kho, cắt khung, màu, mã shop, ghi chú đọc nhãn…): không gửi biên kịch cho đỡ token
_KHOA_KY_THUAT = {"ma", "ten_gio", "goc_ban", "cat_khung", "cat_khung_ly_do", "thoi_luong", "kho_video", "kho_them", "loai_tru", "quy_cach",
                  "shop_product_id", "mau_thuong_hieu", "vai_tro_rieng", "doc_la", "nhan_cung_san_pham", "chua_ro_can_kiem", "su_that_nguon"}


def bai_hoc_cho_loi(ma, toi_da=10):
    """Bài học giám khảo (chung + riêng sản phẩm, dùng lại bai_hoc_cho của đạo diễn) → tối đa toi_da dòng mới nhất liên quan tới lời
    (bỏ dòng dặn việc dựng/hình); không có → ''."""
    try:
        from dao_dien import bai_hoc_cho
        dong = [l.strip() for l in bai_hoc_cho(ma).splitlines()
                if l.startswith("- ") and not _RE_VIEC_DUNG.search(l) and _RE_BAI_HOC_LOI.search(l)]
    except Exception:
        return ""
    return "\n".join(dong[-toi_da:])


def ctx_bien_kich(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None, hieu_qua="", truc=None, loi_truoc=None, sp_day=None):
    """Dữ liệu điền vào mẫu prompt/bien-kich.md (chỗ nào cần logic/khối tuỳ chọn thì tính ở đây; khối rỗng → "").
    truc: [{goc, mo, than, chot, vai}] từng bản (None → chỉ có góc + dạng bài như đề bài cũ). sp_day: hồ sơ đầy đủ (có kho_video) cho khối giọng thật."""
    luat = prompt_mau.doc_luat("LUAT-SAN-XUAT.md")
    luat = luat.split("## Dựng")[0].rstrip()          # phần Dựng là việc của đạo diễn/máy dựng, biên kịch không cần
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    so_gu = so_gu_f.read_text(encoding="utf-8")[-3000:].strip() if so_gu_f.exists() else ""
    so_gu = ("=== SỔ GU CỦA CHỦ HÀNG ===" + chr(10) + so_gu + chr(10)) if so_gu else ""
    # gắn vào khối so_gu (mẫu nào cũng có {{so_gu}}) nên đề bài người dùng đã sửa vẫn nhận bài học, không cần chỗ trống mới trong mẫu
    bh = bai_hoc_cho_loi(sp.get("ma")) if sp.get("ma") else ""
    if bh:
        so_gu += "=== BÀI HỌC GIÁM KHẢO ĐÃ BẮT Ở VIDEO TRƯỚC (viết lời để khỏi lặp lại; đừng viết câu đòi thứ kho không có) ===" + chr(10) + bh + chr(10)
    kg, kat = khung_giay(sp), khung_am_tiet(sp)
    sp_day = sp_day or sp
    dang = list(dang or [])
    if truc is None:
        truc = [{"goc": angles[i] if i < len(angles) else "", "than": dang[i] if i < len(dang) else ""} for i in range(n)]
    else:
        dang = [t.get("than") or "" for t in truc]
        angles = [t.get("goc") or "" for t in truc]
    lt = [x for x in dict.fromkeys(loi_truoc or []) if str(x).strip()][-5:]
    return {
        "luat": luat,
        # mã nội bộ, tên giỏ hàng, mục rỗng và các khoá không giúp viết lời không gửi (goc_ban: chỉ phần góc được giao, nằm trong de_bai)
        "san_pham": json.dumps({k: v for k, v in sp.items() if k not in _KHOA_KY_THUAT and not k.startswith("_") and v not in ("", [], {}, None)},
                               ensure_ascii=False, indent=1),
        "so_gu": so_gu,
        "ban_hang": ban_hang(sp_day.get("ma")),
        "giong_that": giong_that(sp_day) if sp_day.get("kho_video") else "",
        "kho_canh": kho_canh(sp_day["ma"]) if sp_day.get("ma") else "",
        "so_lieu_tiktok": "" if not hieu_qua else chr(10) + "=== SỐ LIỆU THẬT TỪ TIKTOK (video đã đăng) ===" + chr(10) + hieu_qua + chr(10),
        "ten_phai_nhac": json.dumps(ten_phai_nhac(sp_day), ensure_ascii=False),
        "so_ban": n,
        "de_bai": _de_bai(sp_day, truc),
        "loi_truoc": ("BẢN TRƯỚC BỊ LOẠI VÌ:" + chr(10) + chr(10).join("- " + str(x) for x in lt) + chr(10) + chr(10)) if lt else "",
        # khoá của đề bài cũ (người đã tự sửa đề bài vẫn nhận giá trị hợp lý)
        "angles": json.dumps(angles, ensure_ascii=False),
        "dang": json.dumps([f"{d}: {THAN.get(d, '')}" for d in dang], ensure_ascii=False),
        "quy_cach": ("quy_cach = " + json.dumps(qc, ensure_ascii=False) + "  ← bản thứ i nói về QUY CÁCH qc[i] (dung tích/đóng gói), chỉ dùng mức quà của ĐÚNG quy cách đó.") if qc else "",
        "cau_mo_da_dung": json.dumps((mo_dau or [])[-30:], ensure_ascii=False),
        "giay_toi_thieu": f"{kg[0]:g}", "giay_toi_da": f"{kg[1]:g}",
        "am_tiet_toi_thieu": kat[0], "am_tiet_toi_da": kat[1], "am_tiet_muc_tieu": (kat[0] + kat[1]) // 2,
        "cau_toi_thieu": kat[4], "cau_toi_da": kat[5],
        "cau_da_dung": json.dumps(used[-150:], ensure_ascii=False),
        "giong": "|".join(CFG["giong"]["danh_sach"]),
    }


BAN_HANG_CHUNG_TOI_DA = 7000     # ký tự tối đa của tài liệu kiến thức bán hàng chung gửi cho AI
BAN_HANG_RIENG_TOI_DA = 4000     # ... và của hồ sơ bán hàng riêng một sản phẩm (cũng là giới hạn khi lưu)


def _cat_dong(t, toi_da):
    """Cắt ở ranh giới dòng cho khỏi đứt giữa câu."""
    t = t.strip()
    if len(t) <= toi_da:
        return t
    return t[:toi_da].rsplit(chr(10), 1)[0].rstrip()


def _ma_hop_le(ma):
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]+", str(ma or "")))


def duong_dan_ban_hang_rieng(ma):
    if not _ma_hop_le(ma):
        raise ValueError("Mã sản phẩm không hợp lệ")
    return HUB / "san-pham" / str(ma) / "ban-hang.md"


def doc_ban_hang_rieng(ma):
    """Nội dung hồ sơ bán hàng riêng của sản phẩm (san-pham/<ma>/ban-hang.md); chưa có/không đọc được → ""."""
    try:
        return duong_dan_ban_hang_rieng(ma).read_text(encoding="utf-8-sig").replace(chr(13) + chr(10), chr(10)).strip()
    except (OSError, ValueError):
        return ""


def luu_ban_hang_rieng(ma, text):
    """Lưu hồ sơ bán hàng riêng (ghi nguyên tử). Quá BAN_HANG_RIENG_TOI_DA ký tự → ValueError (không cắt lén). Text rỗng → xoá file. → số ký tự đã lưu."""
    f = duong_dan_ban_hang_rieng(ma)
    if not (f.parent / "san-pham.json").is_file():
        raise ValueError("Không tìm thấy sản phẩm")
    t = str(text or "").replace(chr(13) + chr(10), chr(10)).replace(chr(13), chr(10)).strip()
    if len(t) > BAN_HANG_RIENG_TOI_DA:
        raise ValueError(f"Hồ sơ bán hàng dài quá ({len(t)} ký tự, tối đa {BAN_HANG_RIENG_TOI_DA})")
    if not t:
        f.unlink(missing_ok=True)
        return 0
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(t + chr(10), encoding="utf-8", newline=chr(10))
    tmp.replace(f)
    return len(t)


def ban_hang(ma):
    """Khối kiến thức bán hàng cho biên kịch: tài liệu chung (luat/KIEN-THUC-BAN-HANG.md, qua prompt_mau nên theo bản người dùng đã sửa/ghim)
    + hồ sơ bán hàng riêng của sản phẩm. Thiếu phần nào bỏ phần đó; cả hai thiếu → "". Mỗi phần có giới hạn độ dài."""
    out = []
    try:
        chung = prompt_mau.doc_luat("KIEN-THUC-BAN-HANG.md")
    except Exception:
        chung = ""
    for tieu_de, t, toi_da in (("=== KIẾN THỨC BÁN HÀNG (cách nghĩ, không phải khuôn) ===", chung, BAN_HANG_CHUNG_TOI_DA),
                               ("=== HỒ SƠ BÁN HÀNG RIÊNG CỦA SẢN PHẨM ===", doc_ban_hang_rieng(ma), BAN_HANG_RIENG_TOI_DA)):
        t = _cat_dong(t, toi_da)
        if t:
            out.append(tieu_de + chr(10) + t)
    return (chr(10) + chr(10)).join(out) + (chr(10) + chr(10) if out else "")


def gon_hook_thu(x):
    """Các hook biên kịch đã thử và tự chấm: tối đa 3 mục {cau, diem (0–10), vi_sao}. Sai kiểu → [] (không làm hỏng bản)."""
    out = []
    for h in (x if isinstance(x, list) else []):
        if not isinstance(h, dict) or not str(h.get("cau") or "").strip():
            continue
        if len(out) >= 3:
            break
        try:
            d = max(0.0, min(10.0, float(h.get("diem"))))
        except (TypeError, ValueError):
            d = None
        out.append({"cau": re.sub(r"\s+", " ", str(h["cau"])).strip()[:160], "diem": d,
                    "vi_sao": re.sub(r"\s+", " ", str(h.get("vi_sao") or "")).strip()[:160]})
    return out


def gon_don_ban(x, toi_da_tu=20):
    """Đòn bán chính của bài: một câu gọn ≤ 20 từ. Thiếu/sai kiểu → "" (không làm hỏng bản)."""
    if not isinstance(x, str):
        return ""
    t = re.sub(r"\s+", " ", x).strip()
    tu = t.split(" ") if t else []
    if len(tu) > toi_da_tu:
        t = " ".join(tu[:toi_da_tu]).rstrip(" ,;:–-") + "…"
    return t


_Y_HINH_DS = ("viec", "dich", "cay", "bo_phan", "dau_hieu", "tu_khoa")
_Y_HINH_KHOA = _Y_HINH_DS + ("muc", "can_sp", "can_nguoi_noi", "giay")


def gon_y_hinh(x, n_cau):
    """Yêu cầu hình có cấu trúc, đúng 1 phần tử/câu theo thứ tự câu GỐC (kể cả câu sau này bị sentence_times bỏ: khi dùng phải dóng theo chỉ số câu gốc, đừng nén mảng).
    Không phải mảng → None (coi như vắng). Sai độ dài → giữ phần đầu, đệm/cắt bằng {}. Phần tử hỏng → {}. Giá trị enum lạ giữ nguyên chuỗi. Không bao giờ ném lỗi."""
    if not isinstance(x, list):
        return None
    out = []
    for e in x[:n_cau]:
        d = {}
        if isinstance(e, dict):
            for k in _Y_HINH_DS:
                v = e.get(k)
                if isinstance(v, str):
                    v = [v]
                if isinstance(v, list):
                    d[k] = [re.sub(r"\s+", " ", i).strip() for i in v if isinstance(i, str) and i.strip()]
            for k in ("muc", "can_sp"):
                if isinstance(e.get(k), str) and e[k].strip():
                    d[k] = e[k].strip()
            if e.get("can_nguoi_noi") is None or isinstance(e.get("can_nguoi_noi"), bool):
                if "can_nguoi_noi" in e:
                    d["can_nguoi_noi"] = e["can_nguoi_noi"]
            g = e.get("giay")
            if isinstance(g, (int, float)) and not isinstance(g, bool) and 0 <= g < 120:
                d["giay"] = round(float(g), 1)
        out.append(d)
    return out + [{} for _ in range(max(0, n_cau - len(out)))]


def build_prompt(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None, hieu_qua="", truc=None, loi_truoc=None, sp_day=None):
    return prompt_mau.dien("bien-kich", **ctx_bien_kich(sp, n, angles, used, styles, dang, mo_dau, qc, hieu_qua, truc, loi_truoc, sp_day))


# Góc "thương hiệu / nhận dạng chai" (tả nhãn trắng chữ đỏ, dạy nhận chai…) bỏ hẳn theo quyết định của chủ app: content kém.
# Lọc ở đây nên hồ sơ còn ghi các góc này cũng không bao giờ được giao (đề bài chỉ gửi mô tả góc được giao).
GOC_BO = {"thuong-hieu", "nhan-dien-chai", "nhan-dien", "nhan-dang"}
GOC_MAC_DINH = ["cong-dung", "cach-dung", "so-sanh", "qua-tang"]   # sản phẩm mới chưa có góc bán


# Máy kiểm loại câu tả màu bao bì ("nhãn trắng chữ đỏ", "nắp đỏ") hay dạy nhận chai ("coi đúng nhãn", "tem chính hãng").
_RE_NHAN_DANG = re.compile(
    r"(?<!\w)(?:nhãn|chai|can|nắp|vỏ chai|bao bì|chữ|logo|tem)\s+(?:màu\s+)?(?:trắng|đỏ|xanh|vàng|đen|tím|cam|hồng|nâu|bạc)(?!\w)"
    r"|(?<!\w)(?:nhận|coi|xem|nhìn|soi)\s+(?:cho\s+)?(?:đúng|kỹ|kĩ)\s+(?:chai|can|nhãn|tem|logo)(?!\w)"   # không bắt "coi đúng hàng rồi mới trả tiền"
    r"|(?<!\w)tem\s+chính\s+hãng(?!\w)", re.I)


def sp_cho_bien_kich(sp):
    """Hồ sơ gửi biên kịch: bỏ khoá nội bộ, bỏ mô tả nhận dạng bao bì (nhan_dien_chai — đạo diễn vẫn dùng để nhận chai trong cảnh)
    và các sự thật chỉ để dạy nhận chai/tả màu nhãn (góc nhận dạng thương hiệu đã bỏ)."""
    bo = ("kho_video", "loai_tru", "vai_tro_rieng", "cat_khung", "doc_la", "mau_thuong_hieu", "kho_them", "shop_product_id", "nhan_dien_chai")
    out = {k: v for k, v in sp.items() if k not in bo}
    if isinstance(out.get("su_that_duoc_noi"), list):
        out["su_that_duoc_noi"] = [x for x in out["su_that_duoc_noi"]
                                   if not (isinstance(x, str) and (_RE_NHAN_DANG.search(x) or re.search(r"nhận đúng (?:hàng|chai)", x, re.I)))]
    return out


def goc_ban(sp):
    return [g["ma"] for g in sp.get("goc_ban") or [] if g.get("ma") not in GOC_BO] or list(GOC_MAC_DINH)


def ctx_xem_thu(ma, sp, n=3):
    """Dữ liệu thật của sản phẩm cho nút "Xem thử" (chọn góc/kiểu đầu danh sách, không ngẫu nhiên, không ghi sổ trục)."""
    sp_ai = sp_cho_bien_kich(sp)
    goc = goc_ban(sp)
    truc = gan_truc(sp, goc, n, moi_dem(), None, lo_moi(), n, rng=None)
    qcs = [q["ten"] for q in sp.get("quy_cach") or []]
    qc = [qcs[i % len(qcs)] for i in range(n)] if qcs else None
    return ctx_bien_kich(sp_ai, n, [t["goc"] for t in truc], cau_cua_sp(ma), recent_styles(), [t["than"] for t in truc], dem_lich_su(f"mo-dau-{ma}.txt"), qc,
                         _so_lieu(ma), truc=truc, sp_day=sp)


# ---------------------------------------------------------------- kiểm bản viết
def _chuan(s):
    """So tên không phân biệt hoa thường / dấu câu / khoảng trắng: 'NPK 33-11-11' ~ 'npk 33 11 11'."""
    return " " + " ".join(re.findall(r"\w+", (s or "").lower())) + " "


def ten_phai_nhac(sp):
    """Các cách gọi hợp lệ của sản phẩm (lời đọc phải chứa ít nhất 1): tên ngắn, tên gọi, tên khác."""
    ds = [sp.get("ten_ngan"), sp.get("ten_goi")] + list(sp.get("ten_khac") or [])
    ds = [x for x in ds if isinstance(x, str) and x.strip()]
    for x in list(ds):                                   # biến thể bỏ đuôi cỡ gói: "Đạm cá amino can 5l" → "Đạm cá amino" (còn ≥ 3 từ)
        y = _RE_DUOI_GOI.sub("", x).strip()
        if y != x and len(y.split()) >= 3:
            ds.append(y)
    if sp.get("ma") == "nano-dong":
        ds.append("chai nano đồng này")
    return list(dict.fromkeys(ds))


_RE_DUOI_GOI = re.compile(r"\s*\(?\s*(?:can|chai|gói|hộp|xô|bao)\s+\d+(?:[.,]\d+)?\s*(?:ml|kg|lít|l|g)\s*\)?\s*$", re.I)


TAG_OK = {"confident", "warm", "warm, confident", "serious", "matter-of-fact", "curious", "concerned", "surprised", "relieved", "proud", "satisfied",
          "excited", "upbeat", "urgent", "confident, slightly frustrated"}
_RE_DEM_CUOI = re.compile(r"(?<!\w)(?:đó nha|luôn nha|ạ|nha|nè|á|thiệt)\s*$")
_RE_DEM_VAI = re.compile(r"(?<!\w)(?:nha|nè|á)(?!\w)")
_MO_TEN_MUON = {"ket_qua_truoc", "hang_xom", "noi_thiet"}       # mở bằng kết quả/khoảnh khắc: tên sản phẩm được lùi tới câu 3 (cùng kiểu thân chuyen_that_bai)


_RE_TU_HOI = re.compile(r"(?:khách|người ta|bà con|anh chị)\s+(?:hay\s+|cũng\s+|thường\s+)?hỏi\s*:", re.I)
_RE_TRA_LOI_CUT = re.compile(r"^(?:được|có|không|đúng|chắc chắn rồi|vì sao)\s*[.!?]?$", re.I)


_RE_KE_NHAN = re.compile(r"(?<!\w)(?:đọc|nhìn|coi|xem)\s+(?:trên\s+)?nhãn\s+(?:thì\s+)?(?:ta|em|mình|tôi|bà con|anh chị)?\s*(?:sẽ\s+)?thấy(?!\w)", re.I)


def tat_giong_may(item, sp, plain, sents):
    """Tật làm lời đọc nghe như văn viết / máy viết (phần NÓI NHƯ NGƯỜI BÁN NGOÀI CHỢ của đề biên kịch) → danh sách lỗi.
    Chỉ bắt những tật đo chắc được; còn lại để đề bài và giám khảo lo."""
    errs = []
    n_ba_cham = plain.count("…") + plain.count("...")
    if n_ba_cham > 2:
        errs.append(f"{n_ba_cham} dấu '…' (tối đa 2, chỉ ở chỗ ngập ngừng hay nhấn thật)")
    ke = _RE_KE_NHAN.search(plain)
    if ke:
        errs.append(f"kể lể '{ke.group(0)}' nghe quê — nói thẳng thông tin như người bán nói")
    if _RE_TU_HOI.search(plain):
        errs.append("khuôn tự hỏi tự đáp 'Khách hỏi: …?' (kể lại thành lời của người nói)")
    for a, b in zip(sents, sents[1:]):
        if a.rstrip().endswith("?") and (_RE_TRA_LOI_CUT.match(b.strip()) or re.match(r"(?:được|có|không|đúng)\s*,", b.strip().lower())):
            errs.append(f"tự hỏi rồi tự đáp cụt '{b.strip()}'")
            break
    if any(s.rstrip().endswith("?") and re.search(r",\s*hay\s+\w", s.lower()) for s in sents[-2:]):
        errs.append("kết bằng câu hỏi ép chọn 'A, hay B?' (kết bằng một việc cụ thể)")
    # câu cụt (≤ 4 chữ) ở thân bài: giọng AI đọc nghe giật, người nghe hụt ý → gộp vào câu trước; câu mở và câu chốt được ngắn
    cut = [s.strip() for s in sents[1:-1] if len(re.findall(r"\w+", s)) <= 4 and not s.rstrip().endswith("?")]
    if cut:
        errs.append(f"câu cụt ({' / '.join(cut[:3])}) — câu nào cũng phải đủ ý, gộp vào câu trước")
    # luật riêng kiểu: Tên "Nano Đồng Toàn Cầu" (hoặc "chai Nano Đồng này") trong 5 giây đầu → một trong các tên trong ngoặc kép
    # phải lọt vào khoảng âm tiết đầu tương ứng (đọc ~4 âm tiết/giây)
    for luat in sp.get("luat_rieng") or []:
        m = re.search(r"(\d+)\s*giây đầu", str(luat or ""))
        ten = re.findall(r"[\"“]([^\"”]+)[\"”]", str(luat or "")) if m else []
        if ten:
            dau = " ".join(re.findall(r"\w+", plain)[:int(m.group(1)) * 4])
            if not any(_chuan(t) in _chuan(dau) for t in ten):
                errs.append(f"luật riêng: chưa đọc tên \"{ten[0]}\" trong {m.group(1)} giây đầu")
    if (item.get("goc") or "") == "qua-tang" and sp.get("qua_tang") and not re.search(r"(?<!\w)(?:tặng|quà)(?!\w)", plain.lower()):
        errs.append("góc quà tặng nhưng lời đọc không nói quà gì")
    # xưng hô với nhà nông: gọi "các bác", "bà con" thỉnh thoảng; không "tôi", "bạn", "anh chị" (nghe như quảng cáo thành phố)
    low = plain.lower()
    xa = sorted({m.group(0) for m in re.finditer(r"(?<!\w)(?:tôi|anh chị|bạn(?!\w)(?!\s+(?:hàng|bè)))(?!\w)", low)})
    if xa:
        errs.append(f"xưng hô '{', '.join(xa)}' nghe xa lạ — gọi \"các bác\", người kể xưng \"mình\"/\"em\"")
    for goi in ("bà con", "các bác"):
        n_g = len(re.findall(r"(?<!\w)" + goi + r"(?!\w)", low))
        if n_g > 2:
            errs.append(f"{n_g} lần \"{goi}\" (tối đa 2: chỉ gọi chỗ nào tự nhiên, không gọi câu nào cũng gọi)")
    # hook là Ý, không phải tiếng gọi: câu đầu không được mở bằng "Các bác ơi", "Bà con ơi"…
    if sents and re.match(r"\W*(?:các bác|bà con|cô chú|anh em)(?!\w)", sents[0].strip().lower()):
        errs.append(f"câu mở bắt đầu bằng tiếng gọi '{sents[0].strip()[:30]}…' — vào thẳng ý hook, tiếng gọi để chỗ khác")
    return errs


def check(item, sp, used_norm, log=None):
    """→ (lỗi[], các câu). Lỗi không rỗng = loại bản. log(msg): ghi các nhận xét không loại bản."""
    errs = []
    mo, than, chot, vai = (item.get(k) or "" for k in ("mo", "than", "chot", "vai"))
    than = than or item.get("dang") or ""
    # tag: tag ngoài danh sách cho phép → [confident] (không loại); phải có ≥ 3 tag khác nhau
    tags = []
    def _tag(m):
        t = re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", m.group(1).strip().lower()))
        t = t if t in TAG_OK else "confident"
        tags.append(t)
        return f"[{t}]"
    text = re.sub(r"\[([^\]]*)\]", _tag, item.get("text", ""))
    item["text"] = text
    if len(set(tags)) < 3:
        errs.append(f"chỉ {len(set(tags))} tag khác nhau (cần ít nhất 3)")
    plain = re.sub(r"\[[^\]]*\]", "", text)
    n = len(re.findall(r"\w+", plain))
    _lo, _hi, nho, lon, _c1, _c2 = khung_am_tiet(sp)
    if not nho <= n <= lon:
        errs.append(f"{n} âm tiết (máy nhận {nho}–{lon}, nên nhắm {_lo}–{_hi})")
    low = " " + plain.lower() + " "
    for ds, mau in ((CAM_CHU, "từ cấm '{}'"), (VAN_MAU_YEU, "văn mẫu yếu '{}'")):   # khớp nguyên từ, không bắt "nha" trong "nhanh"
        errs += [mau.format(b.strip()) for b in ds if re.search(r"(?<!\w)" + re.escape(b.strip()) + r"(?!\w)", low)]
    m = _RE_NHAN_DANG.search(low)
    if m:
        errs.append(f"tả/dạy nhận dạng bao bì '{m.group(0).strip()}' (góc nhận dạng thương hiệu đã bỏ)")
    sents = [s for s in re.split(r"(?<=[.!?])\s+", plain.strip()) if s.strip()]
    # tên sản phẩm: trong 2 câu đầu (3 câu nếu mở bằng kết quả/khoảnh khắc đang diễn ra hoặc kể chuyện)
    ten = [_chuan(nm) for nm in ten_phai_nhac(sp)]
    han = 3 if mo in _MO_TEN_MUON else 2
    if not any(t in _chuan(plain) for t in ten):
        errs.append("thiếu tên thương hiệu")
    elif not any(t in _chuan(" ".join(sents[:han])) for t in ten):
        errs.append(f"tên sản phẩm chưa xuất hiện trong {han} câu đầu")
    if sents:
        n0 = len(re.findall(r"\w+", sents[0]))
        if n0 > 22:
            errs.append(f"câu mở dài ({n0} âm tiết, tối đa 22)")
        if mo not in ("qua_truoc", "con_so", "rao_viral") and any(_chuan(sents[0]).startswith(t) for t in ten):
            errs.append("câu mở bắt đầu bằng tên sản phẩm")
    # tiếng đệm: tối đa 2 lần ở cuối vế; vai kỹ thuật/dẫn chuyện không dùng nha/nè/á
    dem_dem = sum(1 for v in re.split(r"[.!?…,;:]+", plain) if _RE_DEM_CUOI.search(v.strip().lower()))
    if dem_dem > 2:
        errs.append(f"quá nhiều tiếng đệm cuối vế ({dem_dem} lần, tối đa 2)")
    # giỏ hàng nhắc đúng một lần
    gh = len(re.findall(r"giỏ hàng", plain.lower()))
    if gh == 0:
        errs.append("không nhắc giỏ hàng")
    elif gh >= 3:
        errs.append(f"nhắc giỏ hàng {gh} lần (chỉ một lần)")
    errs += tat_giong_may(item, sp, plain, sents)
    if chot and chot != "qua_cu_the" and log and any(re.search(r"(?<!\w)tặng(?!\w)", s.lower()) for s in sents[-2:]):
        log(f"  lưu ý: kiểu chốt {chot} nhưng hai câu cuối có chữ 'tặng'")
    errs += [f"lặp câu: {s[:30]}" for s in sents if norm(s) in used_norm and len(s.split()) >= 4]
    if item.get("giong") not in CFG["giong"]["danh_sach"]:
        item["giong"] = random.choice(list(CFG["giong"]["danh_sach"]))
    if len(item.get("canh", [])) < len(sents):
        item["canh"] = item.get("canh", []) + [{"vai_tro": ["chai_ro"]}] * (len(sents) - len(item.get("canh", [])))
    pcs = item.get("phong_cach") or [{}]
    item["phong_cach"] = pcs if isinstance(pcs, list) else [pcs]
    return errs, sents


def gon_chu_mo(c, n=30):
    """Chữ móc câu hiện lúc mở: gọn khoảng trắng, cắt ≤ 30 ký tự ở ranh giới từ."""
    c = re.sub(r"\s+", " ", str(c or "")).strip()
    if len(c) > n:
        c = c[:n].rsplit(" ", 1)[0] if " " in c[:n] else c[:n]
    return c.rstrip(" ,;:–-")


def viet(ma_sp, so_ban, log=print):
    sp = json.loads((HUB / "san-pham" / ma_sp / "san-pham.json").read_text(encoding="utf-8"))
    sp_for_ai = sp_cho_bien_kich(sp)
    used_norm = {norm(s) for s in history_sentences()}      # máy chống trùng: câu của mọi sản phẩm
    used = cau_cua_sp(ma_sp)                                 # chỉ để máy biết; đề bài mặc định không gửi 150 câu này nữa
    goc = goc_ban(sp)
    out, tries, loi_truoc = [], 0, []
    dem, lo = moi_dem(ma_sp), lo_moi()
    dem_q = Counter(dem_lich_su(f"qc-{ma_sp}.txt"))
    while len(out) < so_ban and tries < 4:
        tries += 1
        need = min(10, so_ban - len(out))
        hs = {ax: _he_so(ma_sp, ch) for ax, ch in _CHIEU_HIEU_QUA.items()}     # góc/kiểu từng ra nhiều view được xoay tới sớm hơn, chỉ khi số liệu đủ tin
        truc = gan_truc(sp, goc, need, dem, hs, lo, so_ban)
        qcs = [q["ten"] for q in sp.get("quy_cach") or []]
        qc = [_chon(qcs, dem_q, None, random) for _ in range(need)] if qcs else None
        for q in qc or []:
            dem_q[q] += 1
        log(f"  gọi Claude viết {need} bản (lần {tries})…")
        SK.ghi("bien-kich", "nghi", f"Nặn {need} bài (lần {tries})", buoc="goi", so=need, lan=tries)
        try:
            items = lay_json(goi("biên kịch", build_prompt(sp_for_ai, need, [t["goc"] for t in truc], used, recent_styles(), [t["than"] for t in truc],
                                                           dem_lich_su(f"mo-dau-{ma_sp}.txt"), qc, _so_lieu(ma_sp), truc, loi_truoc[-5:], sp))[0])
        except HetHanMuc:
            raise
        except Exception as e:
            log(f"  lỗi: {e}"); continue
        if isinstance(items, dict):                       # AI bọc mảng trong đối tượng → lấy mảng đầu tiên
            items = next((v for v in items.values() if isinstance(v, list)), [items])
        items = [x for x in (items or []) if isinstance(x, dict) and isinstance(x.get("text"), str)]
        for i_it, it in enumerate(items):
            if i_it >= len(truc):
                break
            t = truc[i_it]
            it.update({"goc": t["goc"], "mo": t["mo"], "than": t["than"], "chot": t["chot"], "vai": t["vai"]})   # trục do máy giao là chuẩn, không theo lời AI khai
            errs, sents = check(it, sp, used_norm, log)
            if errs:
                log(f"  loại 1 bản ({it.get('goc')}/{t['mo']}): {'; '.join(errs)}")
                SK.ghi("bien-kich", "nghi", "Loại 1 bài", buoc="loai", kieu=t["mo"], loi=str(errs[0])[:90], so_loi=len(errs))
                _tt = TT.hien_tai()
                if _tt is not None:
                    _tt.them_dong(f"Loại 1 bài: {errs[0]}")          # lý do máy kiểm thật (vd. trùng câu cũ, thiếu tên sản phẩm)
                loi_truoc = [x for x in loi_truoc if x not in errs] + errs      # lý do mới nhất ở cuối; gửi tối đa 5 lý do gần nhất
                continue
            for s in sents:
                used_norm.add(norm(s)); used.append(s)
            it["dang"] = t["than"]
            it["chu_mo"] = gon_chu_mo(it.get("chu_mo"))
            it["don_ban"] = gon_don_ban(it.get("don_ban"))
            it["y_hinh"] = gon_y_hinh(it.get("y_hinh"), len(sents))       # hỏng/thiếu thì thôi, không làm hỏng bản
            it["hook_thu"] = gon_hook_thu(it.get("hook_thu"))
            ten_qc = qc[i_it] if qc and i_it < len(qc) else None
            it["quy_cach"] = next((q["ma"] for q in sp.get("quy_cach") or [] if q["ten"] == ten_qc), None)
            if ten_qc:
                _them_so(f"qc-{ma_sp}.txt", ten_qc)
            def tag(h):                                # #khong dau, khong khoang trang
                import unicodedata
                h = unicodedata.normalize("NFD", str(h).replace("đ", "d").replace("Đ", "D"))
                h = "".join(ch for ch in h if unicodedata.category(ch) != "Mn")
                h = re.sub(r"[^0-9A-Za-z]", "", h).lower()
                return "#" + h if h else ""
            it["hashtag"] = [t_ for t_ in dict.fromkeys(tag(h) for h in (it.get("hashtag") or [])) if t_][:3]
            cap = it.get("caption") or []
            def gon(c, n=90):                          # luật caption ≤ 90 ký tự, cắt ở ranh giới từ
                c = re.sub(r"\s+", " ", str(c)).strip()
                return c if len(c) <= n else c[:n].rsplit(" ", 1)[0].rstrip(",;:–-") + "…"
            it["captions"] = [gon(bo_chet(c)) for c in (cap if isinstance(cap, list) else [cap]) if str(c).strip()] or [""]
            it["caption"] = it["captions"][0]
            for ax in ("goc", "mo", "chot", "vai"):
                _them_so(f"{ax}-{ma_sp}.txt", t[ax])
            _them_so(f"than-{ma_sp}.txt", t["than"])
            _them_so(f"dang-{ma_sp}.txt", t["than"])
            _them_so(f"mo-dau-{ma_sp}.txt", sents[0] if sents else "")
            out.append(it)
            _dh = [h["diem"] for h in it["hook_thu"] if h.get("diem") is not None]
            SK.ghi("bien-kich", "nghi", f"Chốt bài {len(out)}/{so_ban}", buoc="dat", kieu=t["mo"], hook=(sents[0] if sents else "")[:120],
                   diem=max(_dh) if _dh else None, so=len(out), tong=so_ban)
            _tt = TT.hien_tai()
            if _tt is not None:
                _tt.cap(buoc=f"Bài {len(out)}/{so_ban}", tien_do=min(1.0, len(out) / max(1, so_ban)))
                _tt.them_dong(f"Chốt bài {len(out)}/{so_ban}: {sents[0] if sents else ''}")      # câu mở đầu (hook) của bài vừa được nhận
            if len(out) >= so_ban:
                break
    return out
