# 📖 Copia y Restauración Rápida de Odoo 18 (Docker)

Este documento explica cómo **guardar una copia exacta** de un estado de Odoo 18 en Docker (base de datos + filestore + addons) y cómo **levantar esa copia** en caso de fallo del contenedor original o en un clon paralelo para pruebas.

---

## 📂 Archivos a respaldar

Cada copia debe contener:

- **Dump de la base de datos** (`db_<nombreBD>_YYYYMMDD_HHMM.dump.gz`)  
- **Filestore de Odoo** (`filestore_<nombreBD>_YYYYMMDD_HHMM.tgz`)  
- **Carpeta de addons personalizados** (si usas `./addons`)  
- `docker-compose.yml` y `.env`  

Con estos archivos puedes reconstruir tu Odoo en cualquier momento.

---

## 🛠 Script de Backup (Windows PowerShell)

Guarda este script como `backup_odoo.ps1` en tu carpeta de proyecto:

```powershell
param(
  [string]$PgDb = "odoo_test2",   # Nombre real de la BD
  [string]$PgUser = "odoo_test",
  [string]$PgPass = "odoo_test"
)

$DbContainer   = "odoo_n8n_docker-db-1"
$OdooContainer = "odoo_n8n_docker-odoo-1"
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
$bkDir = Join-Path (Get-Location) ("backup_odoo18_" + $stamp)
New-Item -ItemType Directory -Force -Path $bkDir | Out-Null

# 1. Dump BD
docker exec -e PGPASSWORD=$PgPass $DbContainer pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/$PgDb.dump
docker exec $DbContainer bash -lc "gzip -9 /tmp/$PgDb.dump"
docker cp "${DbContainer}:/tmp/$PgDb.dump.gz" "$bkDir\db_${PgDb}_${stamp}.dump.gz"
docker exec $DbContainer rm -f /tmp/$PgDb.dump.gz | Out-Null

# 2. Filestore
$filestorePath = "/var/lib/odoo/.local/share/Odoo/filestore"
docker exec $OdooContainer bash -lc "if [ -d $filestorePath/$PgDb ]; then tar -czf /tmp/filestore_$PgDb.tgz -C $filestorePath $PgDb; fi"
try {
  docker cp "${OdooContainer}:/tmp/filestore_$PgDb.tgz" "$bkDir\filestore_${PgDb}_${stamp}.tgz"
  docker exec $OdooContainer rm -f /tmp/filestore_$PgDb.tgz | Out-Null
} catch {}

Write-Host "✅ Backup completado en: $bkDir"
```

Ejecución:

```powershell
.ackup_odoo.ps1 -PgDb odoo_test2
```

---

## 🛠 Script de Backup (Linux/Mac bash)

Guarda como `backup_odoo.sh` y dale permisos (`chmod +x backup_odoo.sh`):

```bash
#!/bin/bash
PgDb="odoo_test2"   # Nombre real de la BD
PgUser="odoo_test"
PgPass="odoo_test"
DbContainer="odoo_n8n_docker-db-1"
OdooContainer="odoo_n8n_docker-odoo-1"
stamp=$(date +%Y%m%d_%H%M)
bkDir="./backup_odoo18_$stamp"
mkdir -p "$bkDir"

# 1. Dump BD
docker exec -e PGPASSWORD=$PgPass $DbContainer pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/$PgDb.dump
docker exec $DbContainer bash -lc "gzip -9 /tmp/$PgDb.dump"
docker cp ${DbContainer}:/tmp/$PgDb.dump.gz "$bkDir/db_${PgDb}_${stamp}.dump.gz"
docker exec $DbContainer rm -f /tmp/$PgDb.dump.gz

# 2. Filestore
filestorePath="/var/lib/odoo/.local/share/Odoo/filestore"
docker exec $OdooContainer bash -lc "if [ -d $filestorePath/$PgDb ]; then tar -czf /tmp/filestore_$PgDb.tgz -C $filestorePath $PgDb; fi"
docker cp ${OdooContainer}:/tmp/filestore_$PgDb.tgz "$bkDir/filestore_${PgDb}_${stamp}.tgz" 2>/dev/null || echo "No hay filestore"

echo "✅ Backup completado en: $bkDir"
```

Ejecución:

```bash
./backup_odoo.sh
```

---

## 🔄 Restauración en caso de fallo (stack original)

### 1. Levantar stack limpio
```powershell
docker compose down
docker compose up -d
```

### 2. Crear base de datos vacía
```powershell
docker exec -it odoo_n8n_docker-db-1 psql -U odoo_test -c "CREATE DATABASE odoo_test2 OWNER odoo_test;"
```

### 3. Restaurar la base de datos
```powershell
docker cp backup_odoo18_XXXX/db_odoo_test2_XXXX.dump.gz odoo_n8n_docker-db-1:/tmp/odoo.dump.gz
docker exec -it -e PGPASSWORD=odoo_test odoo_n8n_docker-db-1 bash -c "gunzip -c /tmp/odoo.dump.gz | pg_restore -U odoo_test -d odoo_test2 --clean"
docker exec odoo_n8n_docker-db-1 rm -f /tmp/odoo.dump.gz
```

### 4. Restaurar filestore
```powershell
docker cp backup_odoo18_XXXX/filestore_odoo_test2_XXXX.tgz odoo_n8n_docker-odoo-1:/tmp/filestore.tgz
docker exec -it odoo_n8n_docker-odoo-1 bash -c "mkdir -p /var/lib/odoo/.local/share/Odoo/filestore/odoo_test2 && tar -xzf /tmp/filestore.tgz -C /var/lib/odoo/.local/share/Odoo/filestore/odoo_test2 --strip-components=1"
docker exec odoo_n8n_docker-odoo-1 rm -f /tmp/filestore.tgz
```

### 5. Reiniciar servicios
```powershell
docker compose restart
```

### 6. Acceder a Odoo
Abrir en navegador:

```
http://localhost:8069
```

Seleccionar la base `odoo_test2`.  
Listo 🚀.

---

## 🧪 Restauración en un clon paralelo (para pruebas)

También puedes levantar un **clon de Odoo** en paralelo al original, con otros contenedores y puertos, para probar backups sin tocar producción.

### 1. Crear `docker-compose-clone.yml`

```yaml
version: '3.8'

services:
  db_clone:
    image: postgres:16
    container_name: odoo_clone_db
    environment:
      - POSTGRES_USER=odoo_test
      - POSTGRES_PASSWORD=odoo_test
      - POSTGRES_DB=postgres
    ports:
      - "5440:5432"
    volumes:
      - odoo-clone-db-data:/var/lib/postgresql/data
    networks:
      - odoo_clone_network

  odoo_clone:
    image: odoo:18.0
    container_name: odoo_clone_odoo
    depends_on:
      - db_clone
    ports:
      - "8079:8069"
    volumes:
      - odoo-clone-web-data:/var/lib/odoo
      - ./config:/etc/odoo
      - ./addons:/mnt/extra-addons
    environment:
      - HOST=db_clone
      - USER=odoo_test
      - PASSWORD=odoo_test
    networks:
      - odoo_clone_network

networks:
  odoo_clone_network:
    driver: bridge

volumes:
  odoo-clone-web-data:
  odoo-clone-db-data:
```

### 2. Levantar clon

```powershell
docker compose -f docker-compose-clone.yml up -d
```

### 3. Restaurar backup en el clon

```powershell
docker exec -it odoo_clone_db psql -U odoo_test -c "CREATE DATABASE odoo_test2 OWNER odoo_test;"

docker cp backup_odoo18_XXXX/db_odoo_test2_XXXX.dump.gz odoo_clone_db:/tmp/odoo.dump.gz
docker exec -it -e PGPASSWORD=odoo_test odoo_clone_db bash -c "gunzip -c /tmp/odoo.dump.gz | pg_restore -U odoo_test -d odoo_test2 --clean"
docker exec odoo_clone_db rm -f /tmp/odoo.dump.gz

docker cp backup_odoo18_XXXX/filestore_odoo_test2_XXXX.tgz odoo_clone_odoo:/tmp/filestore.tgz
docker exec -it odoo_clone_odoo bash -c "mkdir -p /var/lib/odoo/.local/share/Odoo/filestore/odoo_test2 && tar -xzf /tmp/filestore.tgz -C /var/lib/odoo/.local/share/Odoo/filestore/odoo_test2 --strip-components=1"
docker exec odoo_clone_odoo rm -f /tmp/filestore.tgz
```

### 4. Reiniciar clon

```powershell
docker compose -f docker-compose-clone.yml restart
```

### 5. Acceder al clon

Abrir en navegador:

```
http://localhost:8079
```

Seleccionar la base `odoo_test2`.  
Este clon funciona en paralelo al original.

---

## ✅ Checklist rápido

- [ ] Generar backup con `backup_odoo.ps1` o `backup_odoo.sh`  
- [ ] Conservar `dump` + `filestore` + `docker-compose.yml` + `.env`  
- [ ] En caso de fallo: restaurar en contenedores originales  
- [ ] Para pruebas: restaurar en `docker-compose-clone.yml` con puertos/nombres distintos  

---

Con este flujo tendrás siempre un **estado X guardado** y podrás **levantarlo en minutos** tanto en el entorno original como en un clon paralelo.
