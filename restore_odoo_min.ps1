<# ===================================================================
 RESTORE ODOO SIDE-BY-SIDE (sin borrar tu entorno actual)
=================================================================== #>

param(
  [Parameter(Mandatory = $true)]
  [string]$SnapshotDir,
  [int]$HostPort = 8079,
  [string]$NamePrefix = "odoo-restore",
  [string]$PgDb = "",
  [string]$PgUser = "",
  [string]$PgPass = ""
)

$ErrorActionPreference = "Stop"

function New-RandomSuffix { (Get-Date -Format "yyyyMMdd_HHmmss") }

function Assert-File([string]$pattern, [string]$desc) {
  $f = Get-ChildItem -Path $SnapshotDir -Filter $pattern -ErrorAction SilentlyContinue |
       Sort-Object Name -Descending | Select-Object -First 1
  if (-not $f) { throw "No se encontró $desc con patrón '$pattern' en $SnapshotDir" }
  return $f
}

if (-not (Test-Path $SnapshotDir)) { throw "No existe la carpeta $SnapshotDir" }

# Artefactos
$dump   = Assert-File -pattern "*.dump.gz"   -desc "dump de base de datos (.dump.gz)"
$fs     = Get-ChildItem -Path $SnapshotDir -Filter "filestore_*.tgz"  -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
$roles  = Get-ChildItem -Path $SnapshotDir -Filter "globals_*.sql"    -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
$imgTar = Get-ChildItem -Path $SnapshotDir -Filter "odoo_image_*.tar" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1

# Inferencias
if ([string]::IsNullOrWhiteSpace($PgDb)) {
  if ($dump.Name -match "^db_(?<db>[^_]+)_\d{8}_\d{4}\.dump\.gz$") { $PgDb = $Matches.db }
}
if ([string]::IsNullOrWhiteSpace($PgUser)) { $PgUser = "odoo" }
if ([string]::IsNullOrWhiteSpace($PgUser)) { $PgUser = Read-Host "Usuario de Postgres (p.ej. odoo_test)" }
if ([string]::IsNullOrWhiteSpace($PgDb))   { $PgDb   = Read-Host "Nombre de la BD a restaurar (p.ej. odoo_test2)" }
if ([string]::IsNullOrWhiteSpace($PgPass)) { $PgPass = Read-Host "Password del usuario de Postgres (para el contenedor nuevo)" }

# Nombres (trim para evitar espacios accidentales)
$suffix     = New-RandomSuffix
$netName    = ("{0}_net_{1}" -f $NamePrefix,$suffix).Trim()
$dbName     = ("{0}-db-{1}" -f $NamePrefix,$suffix).Trim()
$odooName   = ("{0}-odoo-{1}" -f $NamePrefix,$suffix).Trim()
$pgVolume   = ("{0}_pgdata_{1}" -f $NamePrefix,$suffix).Trim()
$odooVolume = ("{0}_filestore_{1}" -f $NamePrefix,$suffix).Trim()

Write-Host "-> Puerto host:   $HostPort -> 8069"
Write-Host "-> BD/USER:       $PgDb / $PgUser"

# Red y volúmenes
docker network create $netName | Out-Null
docker volume  create $pgVolume  | Out-Null
docker volume  create $odooVolume| Out-Null

# ---- Postgres (args como array, estable) ----
Write-Host "-> Levantando Postgres ($dbName)..."
$pgArgs = @(
  'run','-d','--name', $dbName,
  '--network', $netName,
  '-e', "POSTGRES_USER=$PgUser",
  '-e', "POSTGRES_PASSWORD=$PgPass",
  '-e', "POSTGRES_DB=$PgDb",
  '-v', "${pgVolume}:/var/lib/postgresql/data",
  'postgres:16'
)
& docker @pgArgs
if ($LASTEXITCODE -ne 0) { throw "Fallo al lanzar Postgres." }

# Esperar disponibilidad
Write-Host "-> Esperando disponibilidad de Postgres (pg_isready)..."
$maxWait = 60; $ok = $false
for ($i=0; $i -lt $maxWait; $i++) {
  docker exec $dbName bash -lc "pg_isready -U $PgUser -d $PgDb" | Out-Null
  if ($LASTEXITCODE -eq 0) { $ok = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ok) { throw "Postgres no respondió a tiempo. Logs: docker logs $dbName" }

# Roles (si existen)
if ($roles) {
  Write-Host "-> Restaurando roles globales..."
  docker cp $roles.FullName "${dbName}:/tmp/roles.sql"
  docker exec -e PGPASSWORD=$PgPass -it $dbName bash -lc "psql -U $PgUser -d postgres -f /tmp/roles.sql" | Out-Null
}

# Restaurar BD desde fichero
Write-Host "-> Copiando dump a contenedor y restaurando BD..."
$dumpInC = "/tmp/restore.dump.gz"
docker cp $dump.FullName "${dbName}:${dumpInC}"

# Recrear BD con comandos separados (sin '&&' ni comillas conflictivas)
docker exec -e PGPASSWORD=$PgPass $dbName dropdb  -U $PgUser --if-exists "$PgDb"
if ($LASTEXITCODE -ne 0) { throw 'Fallo en dropdb.' }
docker exec -e PGPASSWORD=$PgPass $dbName createdb -U $PgUser "$PgDb"
if ($LASTEXITCODE -ne 0) { throw 'Fallo en createdb.' }

# Restaurar dump
docker exec -e PGPASSWORD=$PgPass $dbName bash -lc "gunzip -c ${dumpInC} | pg_restore -U '$PgUser' -d '$PgDb' -v --clean --if-exists"
if ($LASTEXITCODE -ne 0) { throw 'Fallo al restaurar el dump en Postgres.' }

# Imagen de Odoo (limpiar 'Loaded image: ' y espacios/CRLF)
$odooImage = $null
if ($imgTar) {
  Write-Host "-> Cargando imagen snapshot de Odoo desde $($imgTar.Name)..."
  $loadOutLines = docker load -i $imgTar.FullName
  $joined = ($loadOutLines | Out-String)
  if ($joined -match "Loaded image:\s*(?<tag>.+)$") {
    $odooImage = $Matches['tag']
  }
}
if ([string]::IsNullOrWhiteSpace($odooImage)) {
  # Fallback razonable
  $odooImage = (docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -Pattern "^orbalia/odoo18:" | Select-Object -First 1).ToString()
  if ([string]::IsNullOrWhiteSpace($odooImage)) {
    $odooImage = (docker images --format "{{.Repository}}:{{.Tag}}" | Select-Object -First 1).ToString()
  }
}
$odooImage = ($odooImage -replace '\s+$','').Trim()
if ([string]::IsNullOrWhiteSpace($odooImage)) { throw "No se pudo determinar la imagen de Odoo a usar." }
Write-Host "   Imagen a usar: $odooImage"

# ---- Odoo (args como array usando opciones largas con '=') ----
Write-Host "-> Levantando Odoo ($odooName) en puerto $HostPort..."
$odooArgs = @(
  'run','-d',
  '--name', $odooName,
  '--network', $netName,
  "--publish=$HostPort`:8069",
  "--env=HOST=$dbName",
  "--env=USER=$PgUser",
  "--env=PASSWORD=$PgPass",
  "--env=DB=$PgDb",
  "--volume=${odooVolume}:/var/lib/odoo",
  $odooImage
)
& docker @odooArgs
if ($LASTEXITCODE -ne 0) {
  Write-Host "Args de docker run usados:" -ForegroundColor Yellow
  $odooArgs | ForEach-Object { Write-Host "  $_" }
  throw 'Fallo al lanzar el contenedor de Odoo.'
}

# Filestore (si existe)
if ($fs) {
  Write-Host "-> Restaurando filestore desde $($fs.Name)..."
  docker cp $fs.FullName "${odooName}:/tmp/filestore.tgz"
  $bashFs = @'
set -e
mkdir -p /var/lib/odoo/.local/share/Odoo/filestore || true
tar -xzf /tmp/filestore.tgz -C /var/lib/odoo/.local/share/Odoo/filestore || true
chown -R odoo:odoo /var/lib/odoo || true
'@
  docker exec -it $odooName bash -lc "$bashFs"
}

# Logs
Write-Host "-> Comprobando logs iniciales de Odoo (5 s)..."
Start-Sleep -Seconds 5
docker logs --tail 50 $odooName

Write-Host ""
Write-Host "==============================================="
Write-Host "Restauracion en paralelo completada."
Write-Host "URL: http://localhost:$HostPort"
Write-Host "Red: $netName"
Write-Host "DB:  contenedor $dbName  (volumen: $pgVolume)"
Write-Host "FS:  volumen $odooVolume"
Write-Host "Odoo contenedor: $odooName  (imagen: $odooImage)"
Write-Host "==============================================="
