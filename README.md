# 📘 Guía de uso — Snapshots y Restauración de Odoo 18 (Docker)

**Scripts incluidos:**  
- `snapshot_odoo_min.ps1` → Crear snapshot (punto de restauración).  
- `restore_odoo_min.ps1` → Restaurar snapshot.  

**Entorno:** Windows + PowerShell + Docker Compose.

Este README explica cómo crear un **punto de restauración** (BD + filestore + ficheros del host) y cómo volver a ese punto si algo se rompe. Está pensado para el proyecto ubicado en:

```
C:\Github\odoo_n8n_docker
```

con un `docker-compose.yml` que levanta Odoo 18 y PostgreSQL.

---

## 0) Requisitos previos

1. **PowerShell** (verifica que en el prompt veas `PS` al inicio).  
2. **Permitir ejecución de scripts** en la sesión actual:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
   Pulsa **S** (o **O**) para aceptar.  
3. **Docker y Docker Compose** funcionando. Verifica:
   ```powershell
   docker ps
   ```
4. **Rutas de trabajo**: sitúate en la carpeta del proyecto:
   ```powershell
   cd C:\Github\odoo_n8n_docker
   ```

---

## 1) ¿Qué hace cada script?

### `snapshot_odoo_min.ps1` → Crear snapshot
Genera una carpeta `restore_point_YYYYMMDD_HHMM` con:

- `db_<BD>_<stamp>.dump.gz` → **dump** de PostgreSQL.  
- `filestore_<BD>_<stamp>.tgz` → **archivos adjuntos** de Odoo (si existen).  
- `host_files/` → copia de **addons**, **config**, `.env` y `docker-compose.yml`.  

> **Opcional:** si usas `-IncludeImage`, guarda además un `.tar` con la **imagen del contenedor de Odoo** (snapshot binario).

---

### `restore_odoo_min.ps1` → Restaurar snapshot
- Cierra el stack (`docker compose down`) y lo levanta limpio (`up -d`).  
- Restaura la **base de datos** con `pg_restore --clean`.  
- Restaura el **filestore** y ajusta permisos.  
- Reinicia servicios.  

> **Opcional:** si usas `-UseImage`, cargará la **imagen congelada** si está en el snapshot.

---

## 2) Uso de `snapshot_odoo_min.ps1`

### Sintaxis
```powershell
.\snapshot_odoo_min.ps1 `
  -PgDb odoo_test2 `
  [-PgUser odoo_test] `
  [-PgPass odoo_test] `
  [-DbContainer odoo_n8n_docker-db-1] `
  [-OdooContainer odoo_n8n_docker-odoo-1] `
  [-IncludeImage]
```

### Parámetros
- `-PgDb` (obligatorio): base de datos de Odoo (ej. `odoo_test2`).  
- `-PgUser` / `-PgPass`: credenciales PostgreSQL.  
- `-DbContainer`: contenedor de Postgres.  
- `-OdooContainer`: contenedor de Odoo.  
- `-IncludeImage`: guarda la imagen actual del contenedor Odoo en `.tar`.  

### Ejemplo
```powershell
cd C:\Github\odoo_n8n_docker
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\snapshot_odoo_min.ps1 -PgDb odoo_test2
```

### Salida típica
```
Destino: C:\Github\odoo_n8n_docker\restore_point_20251003_1001
Host copiado.
Dump BD OK.
Filestore OK.
----------------------------------------
Snapshot completado.
BD: db_odoo_test2_20251003_1001.dump.gz
Filestore: filestore_odoo_test2_20251003_1001.tgz
Host: host_files
```

---

## 3) Uso de `restore_odoo_min.ps1`

### Sintaxis
```powershell
.\restore_odoo_min.ps1 `
  -SnapshotDir .\restore_point_YYYYMMDD_HHMM `
  [-PgDb odoo_test2] `
  [-PgUser odoo_test] `
  [-PgPass odoo_test] `
  [-DbContainer odoo_n8n_docker-db-1] `
  [-OdooContainer odoo_n8n_docker-odoo-1] `
  [-UseImage]
```

### Parámetros
- `-SnapshotDir` (obligatorio): ruta de la carpeta del snapshot.  
- `-PgDb`, `-PgUser`, `-PgPass`: datos de PostgreSQL.  
- `-DbContainer`, `-OdooContainer`: nombres de contenedores activos.  
- `-UseImage`: carga la imagen congelada del snapshot (si existe).  

### Ejemplo
```powershell
cd C:\Github\odoo_n8n_docker
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\restore_odoo_min.ps1 -SnapshotDir .\restore_point_20251003_1001
```

### Qué hace
1. Baja y sube los contenedores (`docker compose down/up`).  
2. Crea la base de datos si no existe.  
3. Restaura datos desde el dump.  
4. Restaura filestore (si existe).  
5. Reinicia servicios.  

Accede a:  
```
http://localhost:8069
```
Seleccionando la base `odoo_test2`.

---

## 4) Comprobaciones rápidas tras restaurar

- Accede a Odoo → selecciona tu base (`odoo_test2`).  
- Habilita modo desarrollador → Apps → “Actualizar lista” (si instalas módulos).  
- Logs de ayuda:
  ```powershell
  docker logs odoo_n8n_docker-odoo-1 --tail=200
  docker logs odoo_n8n_docker-db-1 --tail=200
  ```

---

## 5) Identificar nombres de contenedores

Comprueba con:
```powershell
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```
y usa los nombres reales en `-DbContainer` y `-OdooContainer`.

---

## 6) Problemas comunes

- **“No se reconoce el archivo .ps1…”** → Estás en `cmd`, no en PowerShell.  
- **“La ejecución de scripts está deshabilitada…”** → Ejecuta `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.  
- **Error en `docker cp "${Contenedor}:/ruta"`** → Ya corregido en el script (usa `${Variable}`).  
- **“No existe contenedor X”** → Ajusta parámetros a los nombres de tu `docker ps`.  
- **No aparece `filestore_*.tgz`** → Normal si no tenías adjuntos aún.  

---

## 7) Buenas prácticas

- Usa **tags fijos de imagen** en `docker-compose.yml` (ej. `odoo:18.0`, `postgres:16`).  
- Haz snapshots frecuentes (antes de cambios críticos o diariamente).  
- Conserva 7–14 snapshots y elimina antiguos.  
- El directorio `host_files` dentro del snapshot guarda tu **estado exacto** del proyecto (addons y config).

---

## 8) Ejemplos rápidos

### Crear snapshot
```powershell
cd C:\Github\odoo_n8n_docker
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\snapshot_odoo_min.ps1 -PgDb odoo_test2
```

### Restaurar el último snapshot
```powershell
cd C:\Github\odoo_n8n_docker
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$last = Get-ChildItem .\restore_point_* | Sort-Object Name -Descending | Select-Object -First 1
.\restore_odoo_min.ps1 -SnapshotDir $last.FullName
```

---

## 9) Estructura de un snapshot

```
restore_point_20251003_1001/
├─ db_odoo_test2_20251003_1001.dump.gz
├─ filestore_odoo_test2_20251003_1001.tgz
└─ host_files/
   ├─ addons/
   ├─ config/
   ├─ .env
   └─ docker-compose.yml
```

Si usaste `-IncludeImage`, verás también:

```
odoo_image_20251003_1001.tar
```

---

## ✅ Conclusión

Con estos dos scripts (`snapshot_odoo_min.ps1` y `restore_odoo_min.ps1`) siempre tendrás un **punto de partida seguro** de tu instancia Odoo 18 en Docker y podrás **volver atrás en minutos** si algo se rompe.
