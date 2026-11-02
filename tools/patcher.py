# -*- coding: utf-8 -*-
"""
《Fighting Fantasy Classics》Bloodbones 简体中文汉化安装器
- 自动定位 Steam 游戏目录，备份原始文件，替换字体资产与书文件
- 可反复运行（幂等）；--restore 一键还原
仅修改本机游戏文件，不联网。
"""
import os, sys, io, json, zlib, shutil, struct, argparse, hashlib, tempfile, glob

APP = "FFC 汉化安装器（Bloodbones 简体中文）"
VER = "1.0"

def _utf8_console():
    try:
        # 固定参数、无用户输入拼接，直接 exec 列表形式，避免 shell 注入
        import subprocess
        subprocess.run(["chcp", "65001"], shell=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

def say(msg=""):
    print(msg, flush=True)

# ---------------- 数据路径（PyInstaller 兼容） ----------------
def data_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(base, "data"), base):
        if os.path.isfile(os.path.join(cand, "font_blob.bin")):
            return cand
    raise SystemExit("找不到补丁数据（data 目录）")

# ---------------- 书籍编解码（XOR 混淆，只动低字节） ----------------
def dec(s):
    return "".join(chr((ord(c) & 0xFF00) | ((((ord(c) & 0xFF) ^ 1) - 0x80) & 0xFF)) for c in s)

def enc(p):
    return "".join(chr((ord(c) & 0xFF00) | ((((ord(c) & 0xFF) + 0x80) & 0xFF) ^ 1)) for c in p)

# ---------------- TMP 字体资产最小解析 ----------------
class R:
    def __init__(s, d): s.d = d; s.o = 0
    def i(s):
        v = struct.unpack_from('<i', s.d, s.o)[0]; s.o += 4; return v
    def q(s):
        v = struct.unpack_from('<q', s.d, s.o)[0]; s.o += 8; return v
    def f(s):
        v = struct.unpack_from('<f', s.d, s.o)[0]; s.o += 4; return v
    def b(s):
        v = s.d[s.o]; s.o += 1; return v
    def align(s): s.o = (s.o + 3) & ~3
    def string(s):
        n = s.i(); v = s.d[s.o:s.o + n].decode('utf-8', 'replace'); s.o += n; s.align(); return v
    def pptr(s): return (s.i(), s.q())

def font_info(raw):
    """返回 name / glyphCount / atlas ppid / atlas 偏移，解析失败返回 None"""
    try:
        r = R(raw)
        r.pptr(); r.b(); r.align(); r.pptr()
        name = r.string()
        r.i(); r.pptr(); r.i(); r.i()
        r.string(); r.f(); r.f(); r.i()
        for _ in range(17): r.f()
        atlas_off = r.o
        fid, pid = r.pptr()
        return {"name": name, "glyphs": r.i(), "atlas": pid, "atlas_off": atlas_off}
    except Exception:
        return None

def set_blob_atlas(blob, ppid):
    b = bytearray(blob)
    r = R(bytes(b)); r.pptr(); r.b(); r.align(); r.pptr(); r.string()
    r.i(); r.pptr(); r.i(); r.i(); r.string(); r.f(); r.f(); r.i()
    for _ in range(17): r.f()
    struct.pack_into('<iq', b, r.o, 0, ppid)
    return bytes(b)

# ---------------- Steam 路径探测 ----------------
def steam_roots():
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            v = winreg.QueryValueEx(k, name)[0]
                            if v: roots.append(v.replace('/', '\\'))
                        except OSError:
                            pass
            except OSError:
                pass
    except Exception:
        pass
    for p in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
              r"D:\Steam", r"D:\SteamLibrary", r"E:\SteamLibrary", r"F:\SteamLibrary"):
        roots.append(p)
    out, seen = [], set()
    for r in roots:
        if r and r.lower() not in seen:
            seen.add(r.lower()); out.append(r)
    return out

def find_game(explicit=None):
    if explicit:
        cands = [explicit]
    else:
        cands = []
        for root in steam_roots():
            vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
            libs = [root]
            if os.path.isfile(vdf):
                try:
                    txt = open(vdf, encoding="utf-8", errors="replace").read()
                    import re
                    for m in re.finditer(r'"path"\s*"([^"]+)"', txt):
                        libs.append(m.group(1).replace('\\\\', '\\'))
                except Exception:
                    pass
            for lib in libs:
                cands.append(os.path.join(lib, "steamapps", "common", "Fighting Fantasy Classics"))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "Fighting Fantasy Classics.exe")):
            return os.path.abspath(c)
        if c and os.path.isdir(os.path.join(c, "Fighting Fantasy Classics_Data")):
            return os.path.abspath(c)
    return None

def local_low_root():
    base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(base, "AppData", "LocalLow", "Tin Man Games", "Fighting Fantasy Classics")

def game_running():
    try:
        import subprocess
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20).stdout
        return "Fighting Fantasy Classics.exe" in out
    except Exception:
        return False

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()

# ---------------- 主流程 ----------------
def do_restore(assets, bookpath, bdir):
    bk_assets = os.path.join(bdir, "sharedassets0.assets.orig")
    bk_book = os.path.join(bdir, "ffhub.bloodbones_book.orig")
    if not os.path.isfile(bk_assets):
        raise SystemExit("[!] 没有找到备份，无法还原。")
    if game_running():
        raise SystemExit("[!] 游戏正在运行，请先退出。")
    shutil.copy2(bk_assets, assets)
    if os.path.isfile(bk_book):
        os.makedirs(os.path.dirname(bookpath), exist_ok=True)
        shutil.copy2(bk_book, bookpath)
    say("\n[完成] 已还原为原始文件（英文原版）。")
    return 0


def main():
    _utf8_console()
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--game", help="游戏安装目录")
    ap.add_argument("--restore", action="store_true", help="还原为原始文件")
    ap.add_argument("--check", action="store_true", help="只检查状态，不改动")
    args = ap.parse_args()

    say("=" * 62)
    say(f" {APP}  v{VER}")
    say("=" * 62)

    import UnityPy
    dd = data_dir()
    blob = open(os.path.join(dd, "font_blob.bin"), "rb").read()
    atlas_z = open(os.path.join(dd, "atlas.z"), "rb").read()
    book = json.load(open(os.path.join(dd, "book_zh.json"), encoding="utf-8"))

    game = find_game(args.game)
    if not game:
        say("\n[!] 没有自动找到游戏目录。")
        try:
            game = input("请把《Fighting Fantasy Classics》安装目录粘贴到这里后回车：\n> ").strip().strip('"')
        except EOFError:
            game = ""
        if not game or not os.path.isdir(game):
            raise SystemExit("目录无效，已退出。")
    data = os.path.join(game, "Fighting Fantasy Classics_Data")
    assets = os.path.join(data, "sharedassets0.assets")
    say(f"\n游戏目录：{game}")
    if not os.path.isfile(assets):
        raise SystemExit(f"[!] 找不到 {assets}，请确认目录选对。")

    low = local_low_root()
    bdir = os.path.join(low, "_hanhua_backup")
    bookpath = os.path.join(low, "ffhub.bloodbones", "ffhub.bloodbones_book")
    os.makedirs(bdir, exist_ok=True)

    # ---- 还原模式 ----
    if args.restore:
        return do_restore(assets, bookpath, bdir)

    # ---- 读当前状态 ----
    env = UnityPy.load(assets)
    fonts, tex_by_pid = [], {}
    for o in env.objects:
        if o.type.name == 'MonoBehaviour':
            info = font_info(o.get_raw_data())
            if info and any(k in info["name"] for k in ("Alegreya",)):
                info["obj"] = o
                fonts.append(info)
        elif o.type.name == 'Texture2D':
            tex_by_pid[o.path_id] = o
    if not fonts:
        raise SystemExit("[!] 这个 assets 里没找到 Alegreya 字体，可能游戏版本不同。")
    regular = next((f for f in fonts if "Regular" in f["name"]), fonts[0])
    atlas_pid = regular["atlas"]
    patched = sum(1 for f in fonts if f["glyphs"] == 4082)
    say(f"字体资产：{len(fonts)} 个，已汉化 {patched} 个；图集 texture pathID={atlas_pid}")
    booksz = os.path.getsize(bookpath) if os.path.isfile(bookpath) else 0
    say(f"书文件：{'已存在 %.1f KB' % (booksz / 1024) if booksz else '尚未生成（首次打开游戏后会自动建）'}")

    if args.check:
        say("\n检查完成，未做任何修改。")
        return 0

    # 无参数双击运行时：已装过则给菜单
    if not sys.argv[1:] and patched >= 3:
        say("\n检测到本作已安装汉化。")
        say("  1 = 重新安装（覆盖）")
        say("  2 = 还原为英文原版")
        say("  3 = 退出")
        try:
            ch = input("\n请输入序号后回车 [默认 3] > ").strip()
        except EOFError:
            ch = "3"
        if ch == "1":
            pass
        elif ch == "2":
            return do_restore(assets, bookpath, bdir)
        else:
            return 0

    if game_running():
        raise SystemExit("\n[!] 游戏正在运行，请先完全退出游戏再安装。")

    # 版本兼容提示：本汉化对应 333 版书
    payload = enc(json.dumps(book, ensure_ascii=False, separators=(',', ':'))).encode('utf-8')
    if os.path.isfile(bookpath):
        try:
            cur = json.loads(dec(open(bookpath, 'rb').read().decode('utf-8')))
            cv = str(cur.get('editor', {}).get('version', '?'))
            if cv not in ('333',):
                say(f"\n[提示] 你本机的书是 {cv} 版，本汉化基于 333 版；仍会覆盖，若出现异常可 --restore 还原。")
        except Exception:
            pass

    # ---- 备份 ----
    bk_assets = os.path.join(bdir, "sharedassets0.assets.orig")
    if not os.path.isfile(bk_assets):
        shutil.copy2(assets, bk_assets)
        say(f"已备份原始字体资产 -> {bk_assets}")
    else:
        say("原始字体资产备份已存在，跳过备份")
    bk_book = os.path.join(bdir, "ffhub.bloodbones_book.orig")
    if os.path.isfile(bookpath) and not os.path.isfile(bk_book):
        if md5(bookpath) == hashlib.md5(payload).hexdigest():
            say("书文件已是汉化版，跳过备份")
        else:
            shutil.copy2(bookpath, bk_book)
            say("已备份原始书文件")

    # ---- 1. 图集 ----
    say("\n[1/3] 写入中文图集（4096x4096，约 16 MB）…")
    raw = zlib.decompress(atlas_z)
    assert len(raw) == 4096 * 4096, "图集尺寸不符"
    tex = tex_by_pid.get(atlas_pid)
    if tex is None:
        raise SystemExit(f"[!] 找不到 pathID={atlas_pid} 的图集纹理")
    td = tex.read_typetree()
    td['m_Width'] = 4096
    td['m_Height'] = 4096
    td['m_TextureFormat'] = 1          # Alpha8
    td['m_CompleteImageSize'] = 4096 * 4096
    td['m_StreamData'] = {'offset': 0, 'size': 0, 'path': ''}
    td['image data'] = raw
    tex.save_typetree(td)

    # ---- 2. 字体 ----
    say("[2/3] 写入 4 套字体（正文 / 加粗 / 斜体 / 描边）…")
    blob2 = set_blob_atlas(blob, atlas_pid)
    names = []
    for f in fonts:
        f["obj"].set_raw_data(blob2)
        names.append(f["name"])
    say("      " + "、".join(names))

    # ---- 3. 材质指向新图集 ----
    say("[3/3] 修正材质引用…")
    fixed = []
    for o in env.objects:
        if o.type.name != 'Material':
            continue
        d = o.read_typetree()
        n = d.get('m_Name', '')
        if not any(k in n for k in ("Alegreya-Italic", "Alegreya-Bold")):
            continue
        sp = d['m_SavedProperties']
        for kv in sp['m_TexEnvs']:
            if kv[0] == '_MainTex':
                kv[1]['m_Texture'] = {'m_FileID': 0, 'm_PathID': atlas_pid}
        o.save_typetree(d)
        fixed.append(n)
    say("      " + ("、".join(sorted(set(fixed))) if fixed else "（无需修改）"))

    tmpd = tempfile.mkdtemp(prefix="ffc_zh_")
    env.save(out_path=tmpd)
    out = os.path.join(tmpd, "sharedassets0.assets")
    if not os.path.isfile(out):
        raise SystemExit("[!] 保存失败")
    shutil.copy2(out, assets)
    shutil.rmtree(tmpd, ignore_errors=True)
    say(f"      已写入 {assets}  ({os.path.getsize(assets)/1048576:.1f} MB)")

    # ---- 书 ----
    say("\n写入中文书文件…")
    os.makedirs(os.path.dirname(bookpath), exist_ok=True)
    open(bookpath, 'wb').write(payload)
    say(f"      {bookpath}  ({len(payload)/1024:.0f} KB)")

    # ---- 校验 ----
    say("\n校验…")
    env2 = UnityPy.load(assets)
    ok_fonts = 0
    for o in env2.objects:
        if o.type.name == 'MonoBehaviour':
            info = font_info(o.get_raw_data())
            if info and "Alegreya" in info["name"] and info["glyphs"] == 4082 and info["atlas"] == atlas_pid:
                ok_fonts += 1
    back = json.loads(dec(open(bookpath, 'rb').read().decode('utf-8')))
    nsec = len([k for k in back if k.startswith('section_')])
    say(f"      汉化字体 {ok_fonts}/4，字形 4082；书 {nsec} 段（应为 639）")
    if ok_fonts < 3 or nsec != 639:
        raise SystemExit("[!] 校验未通过，请把上面的信息反馈给作者。")

    say("\n" + "=" * 62)
    say(" 安装完成！直接启动游戏即可（建议从 Steam 启动）。")
    say(f" 想还原：运行本程序加参数 --restore（备份在 {bdir}）")
    say("=" * 62)
    return 0

if __name__ == "__main__":
    sys.exit(main())
