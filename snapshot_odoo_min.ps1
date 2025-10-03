# Snapshot Odoo 18 (mínimo y robusto)

param(
  [string]$PgDb = "odoo_test2",
  [string]$PgUser = "odoo_test",
  [string]$PgPass = "odoo_test",
  [string]$DbContainer = "odoo_n8n_docker-db-1",
  [string]$OdooContainer = "odoo_n8n_docker-odoo-1",
  [switch]$IncludeImage = $false
)

$ErrorActionPreference = "Stop"

function Exists-Container($name){
  $out = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $name }
  return [bool]$out
}

if(-not (Exists-Container $DbContainer)){ Write-Host "No existe contenedor DB: $DbContainer"; exit 1 }
if(-not (Exists-Container $OdooContainer)){ Write-Host "No existe contenedor Odoo: $OdooContainer"; exit 1 }

$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$dest = Join-Path (Get-Location) ("restore_point_" + $stamp)
$hostDir = Join-Path $dest "host_files"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
New-Item -ItemType Directory -Force -Path $hostDir | Out-Null

Write-Host "Destino: $dest"

# Copias del host
try {
  if(Test-Path ".\.env"){ Copy-Item ".\.env" "$hostDir\" -Force }
  if(Test-Path ".\docker-compose.yml"){ Copy-Item ".\docker-compose.yml" "$hostDir\" -Force }
  if(Test-Path ".\config"){ Copy-Item ".\config" "$hostDir\" -Recurse -Force }
  if(Test-Path ".\addons"){ Copy-Item ".\addons" "$hostDir\" -Recurse -Force }
  Write-Host "Host copiado."
} catch {
  Write-Host "Aviso: no se pudieron copiar algunos archivos del host."
}

# Dump BD
try {
  docker exec -e PGPASSWORD=$PgPass $DbContainer pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/$PgDb.dump
  docker exec $DbContainer bash -lc "gzip -9 /tmp/$PgDb.dump"
  docker cp "${DbContainer}:/tmp/${PgDb}.dump.gz" "$dest\db_${PgDb}_${stamp}.dump.gz"
  docker exec $DbContainer rm -f /tmp/$PgDb.dump.gz | Out-Null
  Write-Host "Dump BD OK."
} catch {
  Write-Host "Error en dump BD: $($_.Exception.Message)"; exit 1
}

# Filestore
$fsPath = "/var/lib/odoo/.local/share/Odoo/filestore"
try {
  docker exec $OdooContainer bash -lc "if [ -d $fsPath/$PgDb ]; then tar -czf /tmp/filestore_$PgDb.tgz -C $fsPath $PgDb; else exit 22; fi"
  docker cp "${OdooContainer}:/tmp/filestore_${PgDb}.tgz" "$dest\filestore_${PgDb}_${stamp}.tgz"
  docker exec $OdooContainer rm -f /tmp/filestore_$PgDb.tgz | Out-Null
  Write-Host "Filestore OK."
} catch {
  if($_.Exception.Message -like "*exit status 22*"){
    Write-Host "Aviso: no hay filestore para $PgDb (puede ser normal)."
  } else {
    Write-Host "Error en filestore: $($_.Exception.Message)"; exit 1
  }
}

# Imagen (opcional)
if($IncludeImage){
  try {
    $tag = "orbalia/odoo18:restore-$stamp"
    docker commit $OdooContainer $tag | Out-Null
    docker save -o "$dest\odoo_image_${stamp}.tar" $tag
    Write-Host "Imagen congelada: $tag"
  } catch {
    Write-Host "Aviso: no se pudo congelar la imagen. Datos guardados igualmente."
  }
}

Write-Host "----------------------------------------"
Write-Host "Snapshot completado."
Write-Host ("BD: db_{0}_{1}.dump.gz" -f $PgDb,$stamp)
if(Test-Path "$dest\filestore_${PgDb}_${stamp}.tgz"){ Write-Host ("Filestore: filestore_{0}_{1}.tgz" -f $PgDb,$stamp) }
Write-Host "Host: host_files"
if($IncludeImage){ Write-Host ("Imagen: odoo_image_{0}.tar" -f $stamp) }
