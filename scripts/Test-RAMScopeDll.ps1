[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$DllPath = "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll",

    [Parameter(Mandatory = $false)]
    [string]$ExportName = "RAMScopeGT150DeviceInit",

    [Parameter(Mandatory = $false)]
    [int]$ExportOrdinal = 14
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not [Environment]::Is64BitProcess) {
    Write-Error "32bit PowerShell では x64 DLL を検証できません。64bit PowerShell で実行してください。"
    exit 2
}

if (-not (Test-Path -LiteralPath $DllPath -PathType Leaf)) {
    Write-Error "DLL が見つかりません: $DllPath"
    exit 3
}

$resolvedPath = (Resolve-Path -LiteralPath $DllPath).ProviderPath

if (-not ("RAMScopeDllProbe" -as [type])) {
    Add-Type @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

public sealed class RAMScopeDllProbeResult
{
    public bool LoadSucceeded { get; set; }
    public long Handle { get; set; }
    public int LoadError { get; set; }
    public string LoadErrorMessage { get; set; }
    public string RequestedPath { get; set; }
    public string LoadedModulePath { get; set; }
    public bool NameFound { get; set; }
    public long NameAddress { get; set; }
    public int NameError { get; set; }
    public string NameErrorMessage { get; set; }
    public bool OrdinalFound { get; set; }
    public long OrdinalAddress { get; set; }
    public int OrdinalError { get; set; }
    public string OrdinalErrorMessage { get; set; }
}

public static class RAMScopeDllProbe
{
    private const uint LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x00000100;
    private const uint LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000;

    [DllImport("kernel32.dll", EntryPoint = "LoadLibraryExW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr LoadLibraryExW(string lpFileName, IntPtr hFile, uint dwFlags);

    [DllImport("kernel32.dll", EntryPoint = "GetProcAddress", CharSet = CharSet.Ansi, ExactSpelling = true, SetLastError = true)]
    private static extern IntPtr GetProcAddressByName(IntPtr hModule, string lpProcName);

    [DllImport("kernel32.dll", EntryPoint = "GetProcAddress", ExactSpelling = true, SetLastError = true)]
    private static extern IntPtr GetProcAddressByOrdinal(IntPtr hModule, IntPtr lpProcName);

    [DllImport("kernel32.dll", EntryPoint = "GetModuleFileNameW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetModuleFileNameW(IntPtr hModule, StringBuilder lpFilename, int nSize);

    [DllImport("kernel32.dll", EntryPoint = "FreeLibrary", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FreeLibrary(IntPtr hModule);

    public static RAMScopeDllProbeResult Probe(string dllPath, string exportName, int ordinal)
    {
        var result = new RAMScopeDllProbeResult { RequestedPath = dllPath };
        uint flags = LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS;

        IntPtr module = LoadLibraryExW(dllPath, IntPtr.Zero, flags);
        int loadError = Marshal.GetLastWin32Error();

        result.Handle = module.ToInt64();
        result.LoadSucceeded = module != IntPtr.Zero;
        result.LoadError = loadError;
        result.LoadErrorMessage = new Win32Exception(loadError).Message;

        if (module == IntPtr.Zero)
        {
            return result;
        }

        try
        {
            var modulePath = new StringBuilder(32768);
            if (GetModuleFileNameW(module, modulePath, modulePath.Capacity) > 0)
            {
                result.LoadedModulePath = modulePath.ToString();
            }

            IntPtr nameAddress = GetProcAddressByName(module, exportName);
            int nameError = Marshal.GetLastWin32Error();
            result.NameAddress = nameAddress.ToInt64();
            result.NameFound = nameAddress != IntPtr.Zero;
            result.NameError = nameError;
            result.NameErrorMessage = new Win32Exception(nameError).Message;

            IntPtr ordinalAddress = GetProcAddressByOrdinal(module, new IntPtr(ordinal));
            int ordinalError = Marshal.GetLastWin32Error();
            result.OrdinalAddress = ordinalAddress.ToInt64();
            result.OrdinalFound = ordinalAddress != IntPtr.Zero;
            result.OrdinalError = ordinalError;
            result.OrdinalErrorMessage = new Win32Exception(ordinalError).Message;

            return result;
        }
        finally
        {
            FreeLibrary(module);
        }
    }
}
'@
}

$result = [RAMScopeDllProbe]::Probe($resolvedPath, $ExportName, $ExportOrdinal)

Write-Host "=== RAMScope DLL Probe ===" -ForegroundColor Cyan
Write-Host "PowerShell 64-bit : $([Environment]::Is64BitProcess)"
Write-Host "Requested path    : $($result.RequestedPath)"
Write-Host "Loaded module path: $($result.LoadedModulePath)"
Write-Host ("Handle            : 0x{0:X}" -f $result.Handle)
Write-Host ""

if (-not $result.LoadSucceeded) {
    Write-Host "NG: DLL ロード失敗" -ForegroundColor Red
    Write-Host ("Load error: {0} (0x{0:X})" -f $result.LoadError)
    Write-Host "Message   : $($result.LoadErrorMessage)"
    exit 10
}

Write-Host "OK: DLL ロード成功" -ForegroundColor Green
Write-Host ""
Write-Host "名前による検索"
Write-Host "  Function: $ExportName"
Write-Host "  Found   : $($result.NameFound)"
Write-Host ("  Address : 0x{0:X}" -f $result.NameAddress)
Write-Host ("  Error   : {0} (0x{0:X})" -f $result.NameError)
Write-Host ""
Write-Host "序数による検索"
Write-Host "  Ordinal : $ExportOrdinal"
Write-Host "  Found   : $($result.OrdinalFound)"
Write-Host ("  Address : 0x{0:X}" -f $result.OrdinalAddress)
Write-Host ("  Error   : {0} (0x{0:X})" -f $result.OrdinalError)

if (-not $result.NameFound -or -not $result.OrdinalFound) {
    exit 11
}

if ($result.NameAddress -ne $result.OrdinalAddress) {
    Write-Warning "名前検索と序数検索で異なるアドレスが返りました。エクスポート定義を再確認してください。"
    exit 12
}

Write-Host ""
Write-Host "PASS: DLL とエクスポート関数を認識しました。" -ForegroundColor Green
exit 0
