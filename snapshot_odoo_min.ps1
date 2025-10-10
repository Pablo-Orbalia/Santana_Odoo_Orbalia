<# ===================================================================
  Snapshot Odoo 18 (reforzado)
  - Autodetecta credenciales de Postgres si no se pasan por parámetro
  - Detecta filestore en /var/lib/odoo/filestore o en .local/share/Odoo/filestore
  - Copia archivos del host (.env, docker-compose.yml, config, addons)
  - Dump BD (custom), dump de roles globales (opcional), filestore
  - Snapshot de imagen del contenedor de Odoo (opcional)
=================================================================== #>

param(
  [string]$PgDb = "",
  [string]$PgUser = "",
  [string]$PgPass = "",
  [string]$DbContainer = "odoo_n8n_docker-db-1",
  [string]$OdooContainer = "odoo_n8n_docker-odoo-1",
  [switch]$IncludeImage = $false,
  [switch]$DumpGlobalRoles = $true
)

$ErrorActionPreference = "Stop"

function Exists-Container($name){
  $out = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $name }
  return [bool]$out
}

if(-not (Exists-Container $DbContainer)){ Write-Host "No existe contenedor DB: $DbContainer"; exit 1 }
if(-not (Exists-Container $OdooContainer)){ Write-Host "No existe contenedor Odoo: $OdooContainer"; exit 1 }

# --- Autodetección de credenciales si no se pasan ---
if([string]::IsNullOrWhiteSpace($PgUser)){
  $PgUser = docker exec $DbContainer bash -lc 'echo -n $POSTGRES_USER'
}
if([string]::IsNullOrWhiteSpace($PgDb)){
  $PgDb = docker exec $DbContainer bash -lc 'echo -n $POSTGRES_DB'
}
if([string]::IsNullOrWhiteSpace($PgPass)){
  $PgPass = docker exec $DbContainer bash -lc 'echo -n $POSTGRES_PASSWORD'
}
if([string]::IsNullOrWhiteSpace($PgUser) -or [string]::IsNullOrWhiteSpace($PgDb)){
  Write-Host "No se pudieron determinar POSTGRES_USER/POSTGRES_DB. Pásalos por parámetro."; exit 1
}

$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$dest = Join-Path (Get-Location) ("restore_point_" + $stamp)
$hostDir = Join-Path $dest "host_files"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
New-Item -ItemType Directory -Force -Path $hostDir | Out-Null

Write-Host "Destino: $dest"
Write-Host "BD: $PgDb · Usuario: $PgUser"

# --- Copias del host ---
try {
  if(Test-Path ".\.env"){ Copy-Item ".\.env" "$hostDir\" -Force }
  if(Test-Path ".\docker-compose.yml"){ Copy-Item ".\docker-compose.yml" "$hostDir\" -Force }
  if(Test-Path ".\config"){ Copy-Item ".\config" "$hostDir\" -Recurse -Force }
  if(Test-Path ".\addons"){ Copy-Item ".\addons" "$hostDir\" -Recurse -Force }
  Write-Host "Archivos del host copiados."
} catch {
  Write-Host "Aviso: no se pudieron copiar algunos archivos del host: $($_.Exception.Message)"
}

# --- Dump BD (formato custom .dump.gz) ---
try {
  docker exec -e PGPASSWORD=$PgPass $DbContainer pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/$PgDb.dump
  docker exec $DbContainer bash -lc "gzip -9 /tmp/$PgDb.dump"
  docker cp "${DbContainer}:/tmp/${PgDb}.dump.gz" "$dest\db_${PgDb}_${stamp}.dump.gz"
  docker exec $DbContainer rm -f /tmp/$PgDb.dump.gz | Out-Null
  Write-Host "Dump de BD generado correctamente."
} catch {
  Write-Host "Error en dump de BD: $($_.Exception.Message)"; exit 1
}

# --- Roles globales (opcional) ---
if($DumpGlobalRoles){
  try {
    docker exec -e PGPASSWORD=$PgPass $DbContainer pg_dumpall -U $PgUser -g > "$dest\globals_${stamp}.sql"
    Write-Host "Exportación de roles globales completada."
  } catch {
    Write-Host "Aviso: no se pudieron exportar roles globales (no crítico): $($_.Exception.Message)"
  }
}

# --- Filestore: detectar ruta válida ---
$fsCandidates = @(
  "/var/lib/odoo/.local/share/Odoo/filestore",
  "/var/lib/odoo/filestore"
)
$fsRoot = $null
foreach($p in $fsCandidates){
  $ok = docker exec $OdooContainer bash -lc "[ -d '$p/$PgDb' ] && echo yes || echo no"
  if($ok -eq "yes"){ $fsRoot = $p; break }
}
try {
  if($null -ne $fsRoot){
    docker exec $OdooContainer bash -lc "tar -czf /tmp/filestore_$PgDb.tgz -C '$fsRoot' $PgDb"
    docker cp "${OdooContainer}:/tmp/filestore_${PgDb}.tgz" "$dest\filestore_${PgDb}_${stamp}.tgz"
    docker exec $OdooContainer rm -f /tmp/filestore_$PgDb.tgz | Out-Null
    Write-Host "Filestore empaquetado desde: $fsRoot"
  } else {
    Write-Host "Aviso: no se encontró filestore para '$PgDb' en rutas conocidas (puede ser normal si es una BD vacía)."
  }
} catch {
  Write-Host "Error al procesar filestore: $($_.Exception.Message)"; exit 1
}

# --- Imagen (opcional) ---
if($IncludeImage){
  try {
    # Evitamos interpolación con ":" usando concatenación
    $tag = "orbalia/odoo18" + ":restore-" + $stamp
    docker commit $OdooContainer $tag | Out-Null
    $imageTar = "$dest\odoo_image_${stamp}.tar"
    docker save -o $imageTar $tag
    Write-Host "Imagen congelada: $tag"
    Write-Host "Guardada en: $imageTar"
  } catch {
    Write-Host "Aviso: no se pudo congelar/guardar la imagen. Los datos (BD/filestore/host) están guardados igualmente. Detalle: $($_.Exception.Message)"
  }
}

# --- README de restauración ---
$readme = @"
RESTAURO RÁPIDO — $stamp
========================
1) Asegúrate de tener el contenedor de Postgres en marcha ($DbContainer) y uno limpio de Odoo ($OdooContainer)
   en la misma red que usas normalmente (la de tu docker-compose).

2) Restaurar BD:
   type `".\db_${PgDb}_${stamp}.dump.gz`" | docker exec -i $DbContainer bash -lc "gunzip -c | pg_restore -U '$PgUser' -d '$PgDb' -v --clean --if-exists"

3) Restaurar filestore (si existe):
   docker cp ".\filestore_${PgDb}_${stamp}.tgz" ${OdooContainer}:/tmp/
   docker exec -it $OdooContainer bash -lc `
     "mkdir -p /var/lib/odoo && `
      ( test -d /var/lib/odoo/.local/share/Odoo || mkdir -p /var/lib/odoo/.local/share/Odoo ) && `
      ( test -d /var/lib/odoo/.local/share/Odoo/filestore || mkdir -p /var/lib/odoo/.local/share/Odoo/filestore ) && `
      tar -xzf /tmp/filestore_${PgDb}_${stamp}.tgz -C /var/lib/odoo/.local/share/Odoo/filestore && `
      chown -R odoo:odoo /var/lib/odoo/.local/share/Odoo/filestore/$PgDb || true"

4) (Opcional) Restaurar roles globales:
   psql -U $PgUser -h <host_db> -d postgres -f ".\globals_${stamp}.sql"

5) Reiniciar Odoo y, si procede, actualizar módulos:
   docker restart $OdooContainer
"@
$readme | Out-File -Encoding UTF8 (Join-Path $dest "README_RESTORE.txt")

Write-Host "----------------------------------------"
Write-Host "Snapshot completado en: $dest"
Write-Host ("BD: db_{0}_{1}.dump.gz" -f $PgDb,$stamp)
if(Test-Path "$dest\filestore_${PgDb}_${stamp}.tgz"){ Write-Host ("Filestore: filestore_{0}_{1}.tgz" -f $PgDb,$stamp) }
if(Test-Path "$dest\globals_${stamp}.sql"){ Write-Host ("Roles: globals_{0}.sql" -f $stamp) }
Write-Host "Host: host_files"
if($IncludeImage){ Write-Host ("Imagen: odoo_image_{0}.tar" -f $stamp) }
