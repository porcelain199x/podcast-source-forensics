param(
    [Parameter(Mandatory = $false)]
    [string]$Path = "."
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $Path).Path
$self = $MyInvocation.MyCommand.Path
$extensions = @(".md", ".yaml", ".yml", ".json", ".csv", ".txt", ".py", ".ps1")
$patterns = [ordered]@{
    "private-key" = "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
    "lark-app-id" = "cli_[A-Za-z0-9]{12,}"
    "lark-resource-token" = "\b(obcn|boxcn|fldcn|wikcn|doccn)[A-Za-z0-9_-]{10,}\b"
    "bearer-token" = "Bearer\s+[A-Za-z0-9._~-]{16,}"
    "secret-assignment" = '(?i)(app[_-]?secret|access[_-]?token|refresh[_-]?token|api[_-]?key)\s*[:=]\s*[''"]?[A-Za-z0-9._~-]{12,}'
    "device-code" = '(?i)device[_-]?code\s*[:=]\s*[''"]?[A-Za-z0-9._~-]{12,}'
    "windows-user-path" = "[A-Za-z]:\\Users\\[^\\\s]+\\"
    "project-absolute-path" = "(?i)[A-Za-z]:\\(newai|\.codex)\\"
}

$findings = @()
$files = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
    $_.FullName -ne $self -and $extensions -contains $_.Extension.ToLowerInvariant()
}

foreach ($file in $files) {
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $file.FullName -Encoding UTF8) {
        $lineNumber++
        foreach ($entry in $patterns.GetEnumerator()) {
            if ($line -match $entry.Value) {
                $findings += [pscustomobject]@{
                    Rule = $entry.Key
                    File = $file.FullName.Substring($root.Length).TrimStart("\")
                    Line = $lineNumber
                }
            }
        }
    }
}

if ($findings.Count -gt 0) {
    $findings | Sort-Object File, Line, Rule | Format-Table -AutoSize
    Write-Output "ERROR: potential secrets or machine-specific identifiers found: $($findings.Count)"
    exit 2
}

Write-Output "OK: no secrets, resource tokens, or machine-specific paths detected in $($files.Count) text files."
exit 0
