#!/opt/build/py311/bin/python3.11
# =============================================================================
# cross_build.py — Build a GENUINE Windows x64 PyInstaller EXE from Linux.
#
# PyInstaller has no official cross-compile support. We run it on Linux
# CPython 3.11 (same minor version as the target Windows CPython 3.11) with:
#   * sys.platform / os.name / platform.* patched to Windows
#   * sys.path / sys.prefix pointing at a REAL Windows CPython 3.11 x64 tree
#     (conda layout), so every module and binary collected into the archive
#     is a Windows one
#   * PyInstaller's isolated-subprocess helper replaced with an in-process
#     shim (it would otherwise try to exec python.exe)
#   * the official Windows x64 bootloaders from the pyinstaller win_amd64
#     wheel
#   * the Win32 resource-API calls (icon/manifest) stubbed; the icon is
#     embedded into the bootloader with lief BEFORE the archive is appended
#   * the tkinter hook's "run a live Tcl interpreter" helpers faked out with
#     the conda tcl/tk paths
# =============================================================================
import os, sys, types, platform, logging
import pathlib  # MUST be imported while os.name is still 'posix' so Path stays
                # PosixPath — otherwise all path joins produce backslashes

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("crossbuild")

BUILD = "/opt/build"
WINPY = f"{BUILD}/mcq/myenv"                        # real Windows CPython 3.11 x64 (conda layout)
PSITE = f"{BUILD}/pysite"                           # linux pyinstaller + win bootloaders
APP   = "/home/user/Ultimate-Free-Proxy-Scrapper-And-Validator"
WORK  = f"{BUILD}/winwork"
DIST  = f"{BUILD}/windist"
EXE_ICON = f"{APP}/icon.ico"
VERSION  = "2.1.0"
PYDLL    = "python311.dll"

# ---------------------------------------------------------------- env faking
def win32_ver(release=None, version=None, csd=None, ptype=None):
    return ("11", "10.0.22631", "SP0", "Multiprocessor Free")

platform.system        = lambda: "Windows"
platform.machine       = lambda: "AMD64"
platform.architecture  = lambda: ("64bit", "")
platform.win32_ver     = win32_ver
platform.win32_edition = lambda: "Enterprise"
platform.mac_ver       = lambda: ("", ("", "", ""), "")
platform.libc_ver      = lambda: ("", "")

os.environ["PROCESSOR_ARCHITECTURE"] = "AMD64"
os.environ["PROCESSOR_LEVEL"] = "6"
os.environ["PROCESSOR_REVISION"] = "3f00"

sys.platform = "win32"
os.name = "nt"
os.pathsep = ";"
# Force posix-flavoured pathlib: all build-time file operations happen on the
# Linux fs; a WindowsPath flavour would join paths with backslashes.
pathlib.Path = pathlib.PosixPath
pathlib.WindowsPath = pathlib.PosixPath
pathlib.PureWindowsPath = pathlib.PurePosixPath

class _DllDirHandle:
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False

os.add_dll_directory = lambda path: _DllDirHandle()  # windows-only os function

sys.executable = f"{WINPY}/python.exe"
sys._base_executable = sys.executable
sys.prefix = sys.base_prefix = WINPY
sys.exec_prefix = sys.base_exec_prefix = WINPY
sys.frozen = False
sys._vpath = "."  # windows-only attr read by the Windows sysconfig
sys.dllhandle = 0  # windows-only; bindepend resolves pythonXY.dll from it

# sys.getwindowsversion() — windows-only; dylib.py checks major >= 10.
# Must behave like a named tuple (ntpath slices it).
import collections as _collections
_WinVersion = _collections.namedtuple(
    "WindowsVersion",
    "major minor build platform service_pack service_pack_major service_pack_minor "
    "platform_version product_type suite_mask",
)
sys.getwindowsversion = lambda: _WinVersion(
    10, 0, 22631, 2, "", 0, 0, (10, 0, 22631), 1, 0x00000000)

os.environ["PATH"] = ";".join([
    WINPY, f"{WINPY}/DLLs", f"{WINPY}/Scripts", f"{WINPY}/Library/bin",
    f"{WINPY}/Lib/site-packages",
    "C:/Windows/System32", "C:/Windows",
])

# Pre-import low-level LINUX extension modules into sys.modules. The build
# driver sometimes executes stdlib imports in-process; those must not try to
# load the Windows .pyd files. (Modulegraph analyzes files statically and
# still collects the real Windows _socket.pyd etc. into the archive.)
import importlib
for _m in ("_socket", "socket", "select", "zlib", "array", "pyexpat",
           "xml.parsers.expat", "_csv", "_queue", "_contextvars",
           "_multibytecodec", "_codecs_cn", "_codecs_jp", "unicodedata",
           "_random", "_bisect", "_sha256", "_sha512", "_sha1", "_md5",
           "_sha3", "_blake2", "_heapq", "_pickle", "_datetime", "_statistics",
           "_typing", "_opcode", "_json", "_struct", "math", "cmath",
           "binascii", "_functools", "_lsprof", "mmap", "audioop"):
    try:
        importlib.import_module(_m)
    except Exception:
        pass

# NOTE: the Linux lib-dynload dir is deliberately NOT on sys.path during
# analysis — otherwise Windows builtins (zlib, _struct, ...) resolve to Linux
# .so files and leak into the archive. The driver's own needs are covered by
# the pre-imported modules above.
sys.path[:] = [
    f"{WINPY}/Lib/site-packages",
    f"{WINPY}/Lib",
    f"{WINPY}/DLLs",
    PSITE,
]

# PyInstaller's get_bootstrap_modules() collects '_struct' and 'zlib' from the
# RUNNING interpreter when they have a __file__ attribute. On Windows they are
# built-ins (inside python311.dll, no __file__), so hide ours behind proxies
# without __file__ — while keeping them functional for the build itself.
class _NoFileModuleProxy(types.ModuleType):
    def __getattr__(self, name):
        if name in ("__file__", "__path__", "__dict__", "__wrapped__"):
            raise AttributeError(name)
        return getattr(self.__wrapped__, name)
    def __dir__(self):
        return [n for n in dir(self.__wrapped__) if n != "__file__"]
for _name in ("_struct", "zlib"):
    _real = sys.modules.get(_name)
    if _real is not None:
        _proxy = _NoFileModuleProxy(_name)
        _proxy.__wrapped__ = _real
        for _k, _v in vars(_real).items():
            if _k != "__file__" and not _k.startswith("__"):
                setattr(_proxy, _k, _v)
        sys.modules[_name] = _proxy
import struct as _struct_mod
if hasattr(_struct_mod, "__file__"):
    _struct_mod.__file__ = str(_struct_mod.__file__)

# Teach the Linux import machinery about Windows extension suffixes (.pyd).
import importlib._bootstrap_external as _be
import importlib.machinery as _mach
_WIN_EXT_SUFFIXES = [".cp311-win_amd64.pyd", ".pyd"]
_orig_gsfloaders = _be._get_supported_file_loaders
def _win_gsfloaders():
    return [
        (_be.ExtensionFileLoader, tuple(_WIN_EXT_SUFFIXES + list(_mach.EXTENSION_SUFFIXES))),
        (_be.SourceFileLoader, _be.SOURCE_SUFFIXES),
        (_be.SourcelessFileLoader, _be.BYTECODE_SUFFIXES),
    ]
_be._get_supported_file_loaders = _win_gsfloaders
sys.path_hooks = [_mach.FileFinder.path_hook(*_win_gsfloaders())] + [
    h for h in sys.path_hooks
]
sys.path_importer_cache.clear()
# original replaced below
_mach.all_suffixes = lambda: list(_mach.EXTENSION_SUFFIXES) + list(_mach.SOURCE_SUFFIXES) + list(_mach.BYTECODE_SUFFIXES)
_mach.EXTENSION_SUFFIXES = tuple(_WIN_EXT_SUFFIXES + list(_mach.EXTENSION_SUFFIXES))

# Windows-only builtins that the Linux interpreter does not know about, plus
# zlib (statically linked into python311.dll on Windows).
# Ground truth from CPython's PC/config.c (statically linked into pythonXY.dll
# on Windows) — matches the conda python311.dll build.
_win_builtins = ('_abc', 'array', '_ast', 'audioop', 'binascii', 'cmath', 'errno',
    'faulthandler', 'gc', 'math', 'nt', '_operator', '_signal', '_md5', '_sha1',
    '_sha256', '_sha512', '_sha3', '_blake2', 'time', '_thread', '_tokenize',
    '_typing', '_statistics', 'msvcrt', '_locale', '_tracemalloc', '_winapi',
    '_codecs', '_weakref', '_random', '_bisect', '_heapq', '_lsprof', 'itertools',
    '_collections', '_symtable', 'mmap', '_csv', '_sre', 'winreg', '_struct',
    '_datetime', '_functools', '_json', 'xxsubtype', '_xxsubinterpreters', 'zlib',
    '_multibytecodec', '_codecs_cn', '_codecs_hk', '_codecs_iso2022', '_codecs_jp',
    '_codecs_kr', '_codecs_tw', '_imp', '_string', '_io', '_pickle', 'atexit',
    '_stat', '_opcode', '_contextvars', 'builtins', 'sys', 'marshal')
sys.builtin_module_names = tuple(sorted(set(sys.builtin_module_names) | set(_win_builtins)))

# ------------------------------------------------- pywin32-ctypes stubbing
for name in ("win32ctypes", "win32ctypes.pywin32",
             "win32ctypes.pywin32.pywintypes", "win32ctypes.pywin32.win32api",
             "win32ctypes.core"):
    m = types.ModuleType(name)
    sys.modules.setdefault(name, m)
sys.modules["win32ctypes"].pywin32 = sys.modules["win32ctypes.pywin32"]
sys.modules["win32ctypes.pywin32"].pywintypes = sys.modules["win32ctypes.pywin32.pywintypes"]
sys.modules["win32ctypes.pywin32"].win32api = sys.modules["win32ctypes.pywin32.win32api"]
# dylib.WinExcludeList asks for the Windows dir at import time
sys.modules["win32ctypes.pywin32.win32api"].GetWindowsDirectory = lambda *a, **k: "C:\\Windows"

# -------- stub ctypes (the build python has no libffi; PyInstaller only
# needs ctypes.util.find_library at build time)
_ct = types.ModuleType("ctypes")
for _n in ("Union", "Structure", "Array", "c_void_p", "c_char_p", "c_wchar_p"):
    setattr(_ct, _n, type(_n, (), {}))
_ct.sizeof = lambda *_a, **_k: 0
_ct.memmove = lambda *_a, **_k: None
_ct.byref = lambda x, *_a: x
_ct.cast = lambda x, *_a, **_k: x
_ct.POINTER = lambda t: t
class _CDLLStub:
    def __init__(self, *a, **k): pass
    def __getattr__(self, name): return lambda *a, **k: 0
_ct.CDLL = _CDLLStub
class _LoaderStub:
    def __getattr__(self, name): return _CDLLStub()
_ct.windll = _LoaderStub()
_ct.cdll = _LoaderStub()
_ct.pydll = _LoaderStub()
_ctu = types.ModuleType("ctypes.util")
_ctu.find_library = lambda name: None
_ct.util = _ctu
sys.modules["ctypes"] = _ct
sys.modules["ctypes.util"] = _ctu

# ------------------------------------- stub Windows-only builtin modules
# The Windows stdlib (shutil etc.) imports builtins like `nt` that exist only
# on Windows. Provide inert stand-ins; the driver never uses their win32 parts.
import importlib
import posix

class _WinBuiltinFinder:
    WIN_MODULES = {"nt", "winreg", "_winapi", "msvcrt", "_wmi", "winsound",
                   "_winapi_cvt", "ntsecuritycon"}
    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.WIN_MODULES:
            import importlib.machinery
            return importlib.machinery.ModuleSpec(fullname, self)
        return None
    def create_module(self, spec):
        m = types.ModuleType(spec.name)
        if spec.name == "nt":
            for attr in dir(posix):
                if not attr.startswith("__"):
                    setattr(m, attr, getattr(posix, attr))
            m._getfinalpathname = lambda p: p
            m._getvolumepathname = lambda p: "C:\\"
            m._getdiskusage = lambda p: (1 << 40, 1 << 39, 1 << 39)
        if spec.name == "_winapi":
            m.GetModuleFileName = lambda h: f"{WINPY}/python311.dll"
            def _winapi_default(name):
                def _noop(*args, **kwargs):
                    return 0
                log.debug("_winapi stub: %s", name)
                return _noop
            m.__dict__["__getattr__"] = _winapi_default
            for k, v in {
                "CREATE_NEW_CONSOLE": 0x10, "CREATE_NEW_PROCESS_GROUP": 0x200,
                "STD_INPUT_HANDLE": -10, "STD_OUTPUT_HANDLE": -11,
                "STD_ERROR_HANDLE": -12, "SW_HIDE": 0,
                "STARTF_USESTDHANDLES": 0x100, "STARTF_USESHOWWINDOW": 0x1,
                "ABOVE_NORMAL_PRIORITY_CLASS": 0x8000,
                "BELOW_NORMAL_PRIORITY_CLASS": 0x4000,
                "HIGH_PRIORITY_CLASS": 0x80, "IDLE_PRIORITY_CLASS": 0x40,
                "NORMAL_PRIORITY_CLASS": 0x20, "REALTIME_PRIORITY_CLASS": 0x100,
                "CREATE_NO_WINDOW": 0x8000000, "DETACHED_PROCESS": 0x8,
                "CREATE_DEFAULT_ERROR_MODE": 0x4000000,
                "CREATE_BREAKAWAY_FROM_JOB": 0x1000000,
                "INFINITE": 0xFFFFFFFF, "WAIT_OBJECT_0": 0, "WAIT_TIMEOUT": 258,
            }.items():
                setattr(m, k, v)
        return m
    def exec_module(self, module):
        pass

sys.meta_path.insert(0, _WinBuiltinFinder())
import importlib.abc, importlib.machinery

# ------------------------------------------------------------- isolated shim
# Pre-register a fake PyInstaller.isolated._parent so the REAL one (which
# imports ctypes and spawns python.exe subprocesses) is never imported.
class _InProcPython:
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def call(self, function, *args, **kwargs):
        return function(*args, **kwargs)

_fake_parent = types.ModuleType("PyInstaller.isolated._parent")
_fake_parent.Python = _InProcPython
_fake_parent.call = lambda function, *a, **k: function(*a, **k)
_fake_parent.decorate = lambda function: function
class SubprocessDiedError(Exception): pass
_fake_parent.SubprocessDiedError = SubprocessDiedError
sys.modules["PyInstaller.isolated._parent"] = _fake_parent

import PyInstaller
from PyInstaller import compat
from PyInstaller import isolated
from PyInstaller.isolated import _parent

assert compat.is_win and compat.system == "Windows" and compat.architecture == "64bit"
assert compat.base_prefix == WINPY, compat.base_prefix
assert compat.is_conda, "conda-meta not detected"
log.info("PyInstaller %s sees: Windows x64 conda python 3.11, prefix=%s",
         PyInstaller.__version__, compat.base_prefix)
compat.EXTENSION_SUFFIXES = tuple(_WIN_EXT_SUFFIXES + list(compat.EXTENSION_SUFFIXES))
compat.ALL_SUFFIXES = list(_mach.all_suffixes())

# Exclude stdlib extensions that exist only as LINUX modules in the driver
# (everything shipped as a real Windows .pyd in DLLs/ stays collectable).
import glob as _glob
_dynload = f"{BUILD}/py311/lib/python3.11/lib-dynload"
LINUX_ONLY_EXCLUDES = []
for so in sorted(_glob.glob(f"{_dynload}/*.so")):
    base = os.path.basename(so).split(".")[0]
    if base == "_ctypes":  # driver-side stub only
        pass
    # Modules without a real Windows .pyd must never be collected from the
    # Linux dynload dir; if they are Windows builtins, they live inside
    # python311.dll and need no archive entry at all.
    has_windows = os.path.exists(f"{WINPY}/DLLs/{base}.pyd")
    if not has_windows:
        LINUX_ONLY_EXCLUDES.append(base)
log.info("Linux-only stdlib extensions excluded: %s", LINUX_ONLY_EXCLUDES)

# belt & braces: point the public names at our in-process class too
_parent.Python = _InProcPython
isolated.Python = _InProcPython
assert isolated.Python is _InProcPython

# ------------------------------------------- stub Win32 resource API calls
import PyInstaller.utils.win32.icon as _pi_icon
import PyInstaller.utils.win32.winresource as _pi_winresource
import PyInstaller.utils.win32.winmanifest as _pi_winmanifest
_pi_winresource.remove_all_resources         = lambda *a, **k: None
_pi_winmanifest.write_manifest_to_executable = lambda *a, **k: None
_pi_icon.CopyIcons                           = lambda *a, **k: None
import PyInstaller.utils.win32.winutils as _pi_winutils
_pi_winutils.update_exe_pe_checksum          = lambda *a, **k: None
import PyInstaller.utils.win32.winresource as _pi_wr  # noqa: F811 (pywintypes.error)
sys.modules["win32ctypes.pywin32.pywintypes"].error = OSError
log.info("Stubbed Win32 resource APIs (icon handled via lief)")

# ---------------------------------------------------- tkinter hook faking
import PyInstaller.utils.hooks.tcl_tk as tcltk_mod

def _fake_get_tcl_tk_info():
    return {
        "available": True,
        "tkinter_extension_file": f"{WINPY}/DLLs/_tkinter.pyd",
        "tcl_version": "8.6",
        "tk_version": "8.6",
        "tcl_threaded": True,
        "tcl_data_dir": f"{WINPY}/Library/lib/tcl8.6",
        "_tcl_runtime_version": "8.6",
    }

tcltk_mod._get_tcl_tk_info = _fake_get_tcl_tk_info
tcltk_mod._check_tkinter_fully_usable = lambda: True
tcltk_mod.tcltk_info._load_tcl_tk_info()   # re-init with the faked info
assert tcltk_mod.tcltk_info.available, "tcltk_info not available!"
log.info("tcl/tk info: tcl_data=%s tk_data=%s tcl_dll=%s tk_dll=%s",
         tcltk_mod.tcltk_info.tcl_data_dir, tcltk_mod.tcltk_info.tk_data_dir,
         tcltk_mod.tcltk_info.tcl_shared_library, tcltk_mod.tcltk_info.tk_shared_library)

# ------------------------------------------------- bootloader icon
def patch_bootloader():
    """Embed icon.ico into the windowed bootloader (RT_ICON + RT_GROUP_ICON).

    PyInstaller normally does this with Win32 resource APIs (unavailable
    here), so we rebuild the bootloader's resource section with lief BEFORE
    the CArchive is appended."""
    import lief, shutil, struct
    src = f"{PSITE}/PyInstaller/bootloader/Windows-64bit-intel/runw.exe"
    ico = open(EXE_ICON, "rb").read()
    _, _, count = struct.unpack("<HHH", ico[:6])
    entries = []
    off = 6
    for _ in range(count):
        w, h, colors, res, planes, bpp, size, doffs = struct.unpack("<BBBBHHII", ico[off:off + 16])
        off += 16
        entries.append((w, h, colors, res, planes, bpp, size, doffs, ico[doffs:doffs + size]))

    binary = lief.parse(src)
    root = lief.PE.ResourceDirectory()
    t_icon = lief.PE.ResourceDirectory(); t_icon.id = 3      # RT_ICON
    t_group = lief.PE.ResourceDirectory(); t_group.id = 14   # RT_GROUP_ICON
    for idx, (w, h, colors, res, planes, bpp, size, doffs, data) in enumerate(entries):
        holder = lief.PE.ResourceDirectory(); holder.id = 1 + idx
        dn = lief.PE.ResourceData(); dn.content = data; dn.id = 1 + idx
        holder.add_child(dn)
        t_icon.add_child(holder)
    grp_holder = lief.PE.ResourceDirectory(); grp_holder.id = 1
    grp = struct.pack("<HHH", 0, 1, count)
    for idx, (w, h, colors, res, planes, bpp, size, doffs, data) in enumerate(entries):
        grp += struct.pack("<BBBBHHIH", w % 256, h % 256, colors, res, planes, bpp, size, 1 + idx)
    gn = lief.PE.ResourceData(); gn.content = grp; gn.id = 1
    grp_holder.add_child(gn)
    t_group.add_child(grp_holder)
    root.add_child(t_icon); root.add_child(t_group)
    binary.set_resources(root)
    binary.write(src + ".patched")

    chk = lief.parse(src + ".patched")
    assert int(chk.header.machine) == 0x8664, chk.header.machine
    assert int(chk.optional_header.subsystem) == 2, chk.optional_header.subsystem
    assert chk.has_resources and len(chk.resources_manager.icons) == count
    shutil.copyfile(src + ".patched", src)
    log.info("Bootloader runw.exe patched with icon.ico (%d sizes)", count)
patch_bootloader()

# ------------------------------------------------------------------ the spec
SPEC = f"""
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['{APP}/main.py'],
    pathex=['{APP}'],
    binaries=[('{WINPY}/Library/bin/vcruntime140.dll', '.'),
              ('{WINPY}/Library/bin/vcruntime140_1.dll', '.')],
    datas=[('{EXE_ICON}', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['flask', 'gunicorn', 'PIL', 'numpy', 'pandas', 'matplotlib',
              'pytest', 'setuptools', 'pip', 'tkinter.test', 'unittest.test',
              'test', 'lib2to3', 'idlelib', 'pydoc_data']
              + {LINUX_ONLY_EXCLUDES!r} + ['_ctypes_test', '_testcapi', '_testimportmultiple',
                                        '_testinternalcapi', '_testmultiphase', 'xxlimited',
                                        'xxlimited_35', 'xxsubtype'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='UltimateProxyScrapper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
"""

os.makedirs(WORK, exist_ok=True)
os.makedirs(DIST, exist_ok=True)
spec_path = f"{WORK}/UltimateProxyScrapper.spec"
with open(spec_path, "w") as f:
    f.write(SPEC)

# --------------------------------------------------------------- run build
from PyInstaller.__main__ import run as pyi_run
import PyInstaller.__main__ as _pi_main
_pi_main.check_unsafe_privileges = lambda: None  # uses win32 API; irrelevant here
pyi_run([
    "--noconfirm",
    "--clean",
    f"--distpath={DIST}",
    f"--workpath={WORK}",
    spec_path,
])

# ---------------------------------------------------------------- validate
exe_path = f"{DIST}/UltimateProxyScrapper.exe"
data = open(exe_path, "rb").read(2)
assert data == b"MZ", "output is not a PE!"

import pefile
pe = pefile.PE(exe_path, fast_load=True)
assert pe.FILE_HEADER.Machine == 0x8664, "not x64!"
assert pe.OPTIONAL_HEADER.Subsystem == 2, "not a GUI app!"
log.info("EXE is a genuine Windows x64 GUI PE: %s (%.1f MB)",
         exe_path, os.path.getsize(exe_path) / 1e6)

from PyInstaller.archive.readers import CArchiveReader
arch = CArchiveReader(exe_path)
toc = arch.toc
names = list(toc.keys()) if isinstance(toc, dict) else [name for name, *_ in toc]
must = [PYDLL, "_tkinter.pyd", "tcl86t.dll", "tk86t.dll"]
for m in must:
    assert any(n == m or n.endswith("/" + m) for n in names), f"missing {m}"
bad = [n for n in names if n.endswith(".so") or "linux" in n.lower()]
assert not bad, f"linux artifacts leaked into archive: {bad}"
tkd = [n for n in names if "_tcl_data" in n or "_tk_data" in n]
log.info("CArchive OK: %d entries (%d tcl/tk data files)", len(names), len(tkd))
log.info("BUILD COMPLETE: %s", exe_path)
