$base = "C:\Users\faiza\Desktop\csv-stats-api"
$dirs = @(
  "backend\api\v1\endpoints",
  "backend\core",
  "backend\services",
  "backend\repositories",
  "backend\workers",
  "backend\ai",
  "backend\profiling",
  "backend\visualization",
  "backend\storage",
  "backend\observability",
  "backend\models",
  "backend\schemas",
  "backend\db\migrations",
  "backend\tests\unit",
  "backend\tests\integration",
  "backend\tests\security",
  "backend\tests\load",
  "frontend\src\pages",
  "frontend\src\components\ui",
  "frontend\src\components\charts",
  "frontend\src\components\dataset",
  "frontend\src\hooks",
  "frontend\src\services",
  "frontend\src\store",
  "frontend\src\charts",
  "frontend\src\layouts",
  "frontend\src\utils",
  "frontend\src\types",
  "infra\docker",
  "infra\k8s",
  "infra\github-actions",
  "docs"
)
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path "$base\$d" | Out-Null
}
Write-Host "All directories created successfully."