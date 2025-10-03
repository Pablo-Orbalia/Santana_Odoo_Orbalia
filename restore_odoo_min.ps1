# Restauración Odoo 18 (mínimo y robusto)

param(
  # Carpeta del snapshot (por ej.: .\restore_point_20251003_1001)
  [Parameter(Mandatory=$true)]
  [string]$SnapshotDir,

  # Parámetros de BD
  [string]$PgDb = "odoo_test2",
  [string]$PgUser = "odoo_test",
  [string]$PgPass = "odoo_test",

  # Nombres reales de contenedores (ajústalos si difieren)
  [string]$DbContainer = "odoo_n8n_docker-db-1",
  [string]$OdooContainer = "odoo_n8n_docker-odoo-1",

  # Si quieres cargar una imagen congelada (si la guardaste con -IncludeImage en el snapshot)
  [switch]$UseImage = $false
)

$ErrorActionPreference = "Stop"

function Exists-Container($name){
  $out = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $name }
  return [bool]$out
}

if(-not (Test-Path $SnapshotDir)){ Write-Host "No existe el directorio de snapshot: $SnapshotDir"; exit 1 }

# 0) Parar stack actual (si está levantado)
Write-Host "⛔ Deteniendo stack actual (docker compose down)..."
try { docker compose down | Out-Null } catch {}

# 1) (Opcional) Cargar imagen congelada y usarla
if($UseImage){
  $img = Get-ChildItem -Path $SnapshotDir -Filter "odoo_image_*.tar" -ErrorAction SilentlyContinue | Select-Object -First 1
  if($img){
    Write-Host "🧊 Cargando imagen congelada: $($img.Name)"
    docker load -i $img.FullName | Out-Null
    # Sugerencia: crear un override para fijar la imagen (si lo necesitas)
    # Nota: aquí solo cargamos la imagen; usar o no un override depende de tu compose.
  } else {
    Write-Host "⚠️  No se encontró odoo_image_*.tar en $SnapshotDir. Continuo sin UseImage."
  }
}

# 2) Levantar stack limpio
Write-Host "🚀 Levantando stack (docker compose up -d)..."
docker compose up -d

# Confirmar contenedores
if(-not (Exists-Container $DbContainer)){ Write-Host "No existe contenedor DB: $DbContainer"; exit 1 }
if(-not (Exists-Container $OdooContainer)){ Write-Host "No existe contenedor Odoo: $OdooContainer"; exit 1 }

# 3) Restaurar BD
Write-Host "🗄  Restaurando base de datos: $PgDb"
# Crear BD si no existe
try {
  docker exec -it $DbContainer psql -U $PgUser -tc "SELECT 1 FROM pg_database WHERE datname='$PgDb';" | Out-Null
} catch {
  # Si no existe, la creamos
}
docker exec -it $DbContainer psql -U $PgUser -c "DO \$\$BEGIN IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '$PgDb') THEN PERFORM dblink_exec('dbname=postgres','CREATE DATABASE $PgDb OWNER $PgUser'); END IF; EXCEPTION WHEN undefined_function THEN PERFORM 1; END; \$\$;" 2>$null | Out-Null
# Alternativa simple: intenta crearla, traga error si existe
try { docker exec -it $DbContainer psql -U $PgUser -c "CREATE DATABASE $PgDb OWNER $PgUser;" | Out-Null } catch {}

# Extensiones útiles (ajusta a tu caso)
try {
  docker exec -it $DbContainer psql -U $PgUser -d $PgDb -c "CREATE EXTENSION IF NOT EXISTS unaccent;" | Out-Null
  docker exec -it $DbContainer psql -U $PgUser -d $PgDb -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" | Out-Null
} catch {}

# Localiza el dump más reciente en el snapshot
$dump = Get-ChildItem -Path $SnapshotDir -Filter ("db_{0}_*.dump.gz" -f $PgDb) | Sort-Object Name -Descending | Select-Object -First 1
if(-not $dump){ Write-Host "❌ No se encontró dump de BD en $SnapshotDir"; exit 1 }

Write-Host "   → Usando dump: $($dump.Name)"
docker cp $dump.FullName "${DbContainer}:/tmp/odoo.dump.gz"
docker exec -e PGPASSWORD=$PgPass -it $DbContainer bash -lc "gunzip -c /tmp/odoo.dump.gz | pg_restore -U $PgUser -d $PgDb --clean"
docker exec $DbContainer rm -f /tmp/odoo.dump.gz | Out-Null

# 4) Restaurar filestore (si existe)
$fs = Get-ChildItem -Path $SnapshotDir -Filter ("filestore_{0}_*.tgz" -f $PgDb) | Sort-Object Name -Descending | Select-Object -First 1
if($fs){
  Write-Host "🗂  Restaurando filestore: $($fs.Name)"
  docker cp $fs.FullName "${OdooContainer}:/tmp/filestore.tgz"
  $fsPath = "/var/lib/odoo/.local/share/Odoo/filestore/$PgDb"
  docker exec -it $OdooContainer bash -lc "mkdir -p $fsPath && tar -xzf /tmp/filestore.tgz -C $fsPath --strip-components=1 && chown -R odoo:odoo $fsPath && rm -f /tmp/filestore.tgz"
} else {
  Write-Host "⚠️  No se encontró archivo de filestore en el snapshot (se continuará sin adjuntos históricos)."
}

# 5) Reiniciar servicios
Write-Host "🔁 Reiniciando servicios..."
docker compose restart | Out-Null

Write-Host ""
Write-Host "✅ Restauración completada."
Write-Host "Abre: http://localhost:8069  → Base: $PgDb"
