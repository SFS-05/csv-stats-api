$base = "C:\Users\faiza\Desktop\csv-stats-api\backend"
$packages = @(
  "",
  "api",
  "api\v1",
  "api\v1\endpoints",
  "core",
  "services",
  "repositories",
  "workers",
  "workers\tasks",
  "ai",
  "profiling",
  "visualization",
  "storage",
  "observability",
  "models",
  "schemas",
  "db",
  "tests",
  "tests\unit",
  "tests\integration",
  "tests\security",
  "tests\load"
)
foreach ($pkg in $packages) {
  if ($pkg -eq "") {
    $path = "$base\__init__.py"
  } else {
    $path = "$base\$pkg\__init__.py"
  }
  if (-not (Test-Path $path)) {
    New-Item -ItemType File -Force -Path $path | Out-Null
    Write-Host "Created: $path"
  }
}
Write-Host "Done."