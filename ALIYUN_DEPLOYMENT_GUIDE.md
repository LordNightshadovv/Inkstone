# Aliyun Deployment & Database Migration Guide

Follow these exact steps to migrate your local changes (especially the database schema updates) to your Aliyun production server safely, **without losing any production data**.

---

## Phase 1: Local Preparation (On Your Mac)

Open your terminal, ensure you are in the `inkstone` folder (`cd ~/inkstone`), and run these commands one by one.

### 1. Generate the Database Migration Script
This detects local schema changes (like `is_initiative` or `frame_color`) and creates a script to apply them to the production database automatically.

```bash
# Ensure your virtual environment is active if you use one
flask db migrate -m "Update schema with new fields"
```
*(If it says `No changes in schema detected.`, you can safely skip to step 2).*

### 2. Commit Your Changes to Git
Let's track these updates in version control.

```bash
git add .
git commit -m "Deploy latest features and database updates"
```

### 3. Push to Your Remote Repository
Push your changes to GitHub / Gitee (whichever you use to store your code).

```bash
git push
```

---

## Phase 2: Production Execution (On Aliyun Server)

Now, we update the production server code and run the database migration. 

### 1. Connect to Your Server
Replace `your_server_ip` with your Aliyun server's IP address and login.

```bash
ssh root@your_server_ip
```
*(Enter your server password if prompted).*

### 2. Navigate to the Inkstone Application Folder
If your code is in `/var/www/inkstone` or `/root/inkstone`, go there. Modify the path if necessary.

```bash
cd /root/inkstone
# OR
cd /var/www/inkstone
```

### 3. Pull the Latest Code
Download the code changes we just pushed.

```bash
git pull
```

### 4. Apply Database Migrations (CRITICAL STEP)
This command will safely apply the new database structure (adding columns) **without deleting any of your existing users, posts, or images**.

```bash
# Ensure you are using the correct Python environment
# If using a virtual environment (e.g., venv), activate it first:
# source venv/bin/activate

flask db upgrade
```

### 5. Restart the Application
For your changes to take effect, restart the python/flask application. Choose the command you normally use:

**If running via Systemd (Gunicorn):**
```bash
sudo systemctl restart inkstone
```

**If running via PM2:**
```bash
pm2 restart inkstone
```

**If running via Supervisor:**
```bash
sudo supervisorctl restart inkstone
```

---

## Phase 3: Verification
Visit your production website and try out the new features (like adjusting the `frame_color` or adding an `is_initiative` project). 

**Done! Your Aliyun server and database are now fully up to date.**
