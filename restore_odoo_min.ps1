param(
  # Carpeta del snapshot (por ej.: .\restore_point_20251003_1001)
  [Parameter(Mandatory=$true)]
  [string]$SnapshotDir,

  # Parametros de BD
  [string]$PgDb = "odoo_test2",
  [string]$PgUser = "odoo_test",
  [string]$PgPass = "odoo_test",

  # Nombres reales de contenedores (ajustalos si difieren)
  [string]$DbContainer = "odoo_n8n_docker-db-1",
  [string]$OdooContainer = "odoo_n8n_docker-odoo-1",

  # Si quieres cargar una imagen congelada (si la guardaste con -IncludeImage en el snapshot)
  [switch]$UseImage = $false
)

$ErrorActionPreference = "Stop"

function Exists-Container($name) {
  $out = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $name }
  return [bool]$out
}

if (-not (Test-Path $SnapshotDir)) {
  Write-Host "No existe el directorio de snapshot: $SnapshotDir"
  exit 1
}

# 0) Parar stack actual
Write-Host "[1/6] Deteniendo stack: docker compose down"
try { docker compose down | Out-Null } catch {}

# 1) (Opcional) Cargar imagen congelada
if ($UseImage) {
  $img = Get-ChildItem -Path $SnapshotDir -Filter "odoo_image_*.tar" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($img) {
    Write-Host "[2/6] Cargando imagen congelada: $($img.Name)"
    docker load -i $img.FullName | Out-Null
  } else {
    Write-Host "[2/6] No se encontro odoo_image_*.tar en $SnapshotDir. Continuo sin UseImage."
  }
} else {
  Write-Host "[2/6] Omitido: carga de imagen congelada"
}

# 2) Levantar stack limpio
Write-Host "[3/6] Levantando stack: docker compose up -d"
docker compose up -d

# Confirmar contenedores
if (-not (Exists-Container $DbContainer)) {
  Write-Host "No existe contenedor DB: $DbContainer"
  exit 1
}
if (-not (Exists-Container $OdooContainer)) {
  Write-Host "No existe contenedor Odoo: $OdooContainer"
  exit 1
}

# 3) Restaurar BD (AUTODETECCION)
Write-Host "[4/6] Preparando base de datos: $PgDb"

# Crear BD limpia (DROP/CREATE)
try {
  docker exec -i $DbContainer psql -U $PgUser -d postgres -c "DROP DATABASE IF EXISTS $PgDb;" | Out-Null
  docker exec -i $DbContainer psql -U $PgUser -d postgres -c "CREATE DATABASE $PgDb OWNER $PgUser;" | Out-Null
} catch {
  Write-Host "Aviso: error creando BD (continuo): $_"
}

# Localizar el dump mas reciente (segun tu snapshot actual termina en .dump.gz)
$dump = Get-ChildItem -Path $SnapshotDir -Filter ("db_{0}_*.dump.gz" -f $PgDb) | Sort-Object Name -Descending | Select-Object -First 1
if (-not $dump) {
  Write-Host "No se encontro dump de BD (db_${PgDb}_*.dump.gz) en $SnapshotDir"
  exit 1
}
Write-Host ("Usando dump: {0}" -f $dump.Name)

# Copiar al contenedor para poder inspeccionarlo
docker cp $dump.FullName "${DbContainer}:/tmp/odoo.dump"

# Autodetectar formato:
# - GZIP: cabecera 0x1F 0x8B -> "31 139"
# - Formato personalizado pg_dump: empieza por "PGDMP"
$magicBytes = ([System.IO.File]::ReadAllBytes($dump.FullName))[0..1] -join ' '
$gzipHeader = ($magicBytes -eq '31 139')

if ($gzipHeader) {
  # dump.gz real -> descomprimir y restaurar con pg_restore
  docker exec -e PGPASSWORD=$PgPass -i $DbContainer bash -lc "gunzip -c /tmp/odoo.dump | pg_restore --clean -U $PgUser -d $PgDb"
} else {
  # No es gzip. Comprobar si es formato personalizado (PGDMP) o SQL plano
  $head5 = -join (Get-Content $dump.FullName -Encoding Byte -TotalCount 5 | ForEach-Object {[char]$_})
  if ($head5 -eq 'PGDMP') {
    docker exec -e PGPASSWORD=$PgPass -i $DbContainer bash -lc "gunzip -c /tmp/odoo.dump | pg_restore --clean --if-exists -U $PgUser -d $PgDb"
  } else {
    docker exec -e PGPASSWORD=$PgPass -i $DbContainer bash -lc "psql -U $PgUser -d $PgDb < /tmp/odoo.dump"
  }
}

# Limpiar archivo temporal del contenedor
docker exec $DbContainer rm -f /tmp/odoo.dump | Out-Null

# Crear extensiones utiles (por si no vienen en el dump)
try {
  docker exec -i $DbContainer psql -U $PgUser -d $PgDb -c "CREATE EXTENSION IF NOT EXISTS unaccent;" | Out-Null
  docker exec -i $DbContainer psql -U $PgUser -d $PgDb -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" | Out-Null
} catch {
  Write-Host "Aviso: no se pudieron crear extensiones (continuo): $_"
}

# 4) Restaurar filestore (AUTODETECCION)
$fs = Get-ChildItem -Path $SnapshotDir -Filter ("filestore_{0}_*.tgz" -f $PgDb) | Sort-Object Name -Descending | Select-Object -First 1
if ($fs) {
  Write-Host "[5/6] Restaurando filestore: $($fs.Name)"
  docker cp $fs.FullName "${OdooContainer}:/tmp/filestore.arc"
  $fsPath = "/var/lib/odoo/.local/share/Odoo/filestore/$PgDb"

  # Detecta si el .tgz está gzip o es tar plano
  $fsMagic = ([System.IO.File]::ReadAllBytes($fs.FullName))[0..1] -join ' '
  if ($fsMagic -eq '31 139') {
    docker exec -u root -i $OdooContainer bash -lc "rm -rf $fsPath && mkdir -p $fsPath && tar -xzf /tmp/filestore.arc -C $fsPath --strip-components=1 && chown -R odoo:odoo $fsPath && rm -f /tmp/filestore.arc"
  } else {
    docker exec -u root -i $OdooContainer bash -lc "rm -rf $fsPath && mkdir -p $fsPath && tar -xf  /tmp/filestore.arc -C $fsPath --strip-components=1 && chown -R odoo:odoo $fsPath && rm -f /tmp/filestore.arc"
  }
} else {
  Write-Host "[5/6] No se encontro archivo de filestore en el snapshot (continuo sin adjuntos historicos)."
}


# 5) Reiniciar servicios
Write-Host "[6/6] Reiniciando servicio de Odoo"
docker compose restart odoo | Out-Null

Write-Host ""
Write-Host "OK: Restauracion completada."
Write-Host ("Abrir: http://localhost:8069  -> Base: {0}" -f $PgDb)
