# LNMP 一键安装包

LNMP 是一个使用 Linux Shell 编写的一键安装工具，可在 Linux VPS 或独立服务器上编译安装以下生产环境：

| 模式 | 组件 |
| --- | --- |
| LNMP | Nginx + MySQL/MariaDB + PHP |
| LNMPA | Nginx + MySQL/MariaDB + PHP + Apache |
| LAMP | Apache + MySQL/MariaDB + PHP |

支持 CentOS、RHEL、Fedora、Debian、Ubuntu、Raspbian、Deepin、Alibaba、Amazon、Mint、Oracle、Rocky、Alma、Kali、UOS、银河麒麟、openEuler、Anolis OS、OpenCloudOS、Huawei Cloud EulerOS 等发行版。

- 官网：[lnmp.org](https://lnmp.org)
- 作者：licess（[admin@lnmp.org](mailto:admin@lnmp.org)）
- 问题反馈与技术支持：[LNMP 论坛](https://bbs.lnmp.com/forum-25-1.html)
- 支持项目：[打赏捐赠](https://lnmp.org/donation.html)

## 目录

- [主要功能](#主要功能)
- [安装](#安装)
- [自定义配置](#自定义配置)
- [升级](#升级)
- [扩展插件](#扩展插件)
- [其他组件与工具](#其他组件与工具)
- [运行管理](#运行管理)
- [常用路径](#常用路径)
- [下载源与 SHA256 评估记录](#下载源与-sha256-评估记录)

## 主要功能

- 自定义 Nginx、PHP 编译参数，以及网站和数据库目录。
- 生成 Let's Encrypt、ZeroSSL、BuyPass 免费 SSL 证书。
- 无人值守安装；LNMP 模式支持安装多个 PHP 版本。
- 单独安装 Nginx、MySQL/MariaDB 或 PureFTPd。
- 管理虚拟主机、数据库、FTP 用户和 SSL 证书。
- 升级 Nginx、MySQL/MariaDB、PHP 和 phpMyAdmin。
- 安装 PHP 扩展及 Redis、Memcached、XCache 等组件。
- 提供数据库密码重置、502 自动重启、日志切割、SSH 防护和备份脚本。

## 安装

### 准备环境

安装前请确认已有 `wget`。如果提示 `wget: command not found`，按系统使用以下命令之一：

```bash
# CentOS/RHEL 等系统
yum install wget

# Debian/Ubuntu 等系统
apt-get install wget
```

建议先启动 `screen` 会话，以便断线后恢复：

```bash
screen -S lnmp
```

### 下载并安装

```bash
wget https://soft.lnmp.com/lnmp/lnmp2.2.tar.gz -cO lnmp2.2.tar.gz
tar zxf lnmp2.2.tar.gz
cd lnmp2.2
./install.sh lnmp
```

根据需要选择安装模式：

| 命令 | 安装模式 |
| --- | --- |
| `./install.sh lnmp` | LNMP |
| `./install.sh lnmpa` | LNMPA |
| `./install.sh lamp` | LAMP |

断线后可执行 `screen -r lnmp` 恢复会话。完整步骤见 [安装教程](https://lnmp.org/install.html)。

以下命令均在 LNMP 安装包目录下执行，例如 `lnmp2.2`。

### 版本与默认配置

LNMP 2.2 默认选择 MySQL 8.4 LTS 与 PHP 8.3，可选 PHP 8.4/8.5、MariaDB 11.4/11.8 LTS、OpenSSL 3.x、Nginx 1.30、Apache 2.4.67、phpMyAdmin 5.2.3 等版本。

SSL 模板默认启用 TLSv1.2/TLSv1.3；下载流程默认校验证书，并支持通过 [src/checksums.sha256](src/checksums.sha256) 增加 SHA256 校验。各批次换源对比、兼容性和验证范围见文末的[评估记录](#下载源与-sha256-评估记录)。

### 无人值守安装

参见 [无人值守安装教程](https://lnmp.org/faq/v1-5-auto-install.html)。

## 自定义配置

编辑 [lnmp.conf](lnmp.conf)，可设置下载服务器地址、网站及数据库目录，并添加 Nginx、PHP 编译参数。安装和升级都会读取该文件，修改后建议备份。

详细参数见 [lnmp.conf 配置说明](https://lnmp.org/faq/lnmp-software-list.html#lnmp.conf)。

## 升级

执行以下命令，按提示选择组件：

```bash
./upgrade.sh
```

也可直接指定目标，例如：

```bash
./upgrade.sh nginx
```

| 参数 | 用途 |
| --- | --- |
| `nginx` | 升级 Nginx，可指定版本 |
| `mysql` | 升级 MySQL |
| `mariadb` | 升级 MariaDB |
| `m2m` | 将 MySQL 升级为 MariaDB |
| `php` | 升级主 PHP，仅适用于 LNMP |
| `phpa` | 升级 LNMPA/LAMP 的 PHP |
| `mphp` | 升级多 PHP 环境中的同一大版本，例如 7.2.x → 7.2.x；跨大版本需另行安装 |
| `phpmyadmin` | 升级 phpMyAdmin |

> MySQL/MariaDB 升级风险较大。脚本虽会自动备份数据，仍建议在操作前自行备份。

## 扩展插件

使用 `addons.sh` 安装或卸载扩展，例如：

```bash
./addons.sh install apcu
./addons.sh uninstall apcu
```

命令格式：

```text
./addons.sh {install|uninstall} <扩展参数>
```

### 缓存与加速

| 参数 | 说明 | 管理界面 |
| --- | --- | --- |
| `xcache` | 安装 XCache，按提示选择版本并设置密码；管理用户名为 `admin` | `http://yourIP/xcache/` |
| `redis` | 安装 Redis 及 PHP 扩展 | `http://yourIP/redis.php` |
| `memcached` | 安装 Memcached，可选择 PHP memcache 或 memcached 扩展 | `http://yourIP/memcached.php` |
| `opcache` | 安装或配置 OPcache | `http://yourIP/ocp.php` |
| `eaccelerator` | 安装 eAccelerator | — |
| `apcu` | 安装 APCu PHP 扩展 | `http://yourIP/apc.php` |

> 请勿安装多个缓存类扩展模块，以免网站出现问题。

### PHP 模块

| 参数 | 用途与要求 |
| --- | --- |
| `exif` | 读取图片 Exif 信息 |
| `fileinfo` | 读取文件 MIME 类型与编码；安装要求至少 1 GB 内存 |
| `ldap` | LDAP 扩展 |
| `bz2` | bzip2 压缩扩展 |
| `sodium` | Sodium 加密扩展；PHP 7.2 以下需通过 `addons.sh` 安装，不能通过 `lnmp.conf` 开启 |
| `imap` | IMAP 扩展 |
| `swoole` | PHP 协程框架模块；不能通过 `lnmp.conf` 开启安装 |

### 图像处理与加载器

| 参数 | 组件 | 安装位置／说明 |
| --- | --- | --- |
| `imagemagick` | ImageMagick + Imagick PHP 扩展 | `/usr/local/imagemagick/bin/` |
| `ioncube` | ionCube Loader | 用于运行加密 PHP 程序 |
| `sg` | SourceGuardian Loader | 旧版本包的来源与可用性见 [SourceGuardian 评估](#sourceguardian-历史加载器) |

## 其他组件与工具

### 多 PHP 版本

仅支持 LNMP 模式：

```bash
./install.sh mphp
```

添加虚拟主机时，通过 `lnmp vhost add` 选择 PHP 版本；也可以将 Nginx 虚拟主机配置中的 `include enable-php.conf` 改为对应版本，例如：

```nginx
include enable-php8.4.conf;
```

其中 `8.4` 替换为已安装的 PHP 大版本号，例如 `5.6`、`7.4` 或 `8.3`。

### 单独安装组件

| 命令 | 用途 |
| --- | --- |
| `./install.sh db` | 单独安装 MySQL 或 MariaDB |
| `./install.sh nginx` | 单独安装 Nginx |
| `./pureftpd.sh` | 安装 PureFTPd；通过 `lnmp ftp` 管理用户 |

### 实用脚本

以下脚本位于 [tools/](tools/) 目录，可复制到其他目录运行。

| 脚本 | 用途 |
| --- | --- |
| `reset_mysql_root_password.sh` | 重置 MySQL/MariaDB 的 root 密码 |
| `check502.sh` | 检测 PHP-FPM 异常并自动重启，可配合 crontab 使用 |
| `cut_nginx_logs.sh` | 切割 Nginx 日志 |
| `remove_disable_function.sh` | 取消被禁用的 PHP 函数 |
| `backup.sh` | 备份 |
| `denyhosts.sh` | DenyHosts SSH 防护 |
| `fail2ban.sh` | Fail2Ban 防护 |

## 运行管理

### 服务状态

| 服务 | 命令 | 支持的操作 |
| --- | --- | --- |
| 整套环境 | `lnmp <操作>` | `start`、`stop`、`reload`、`restart`、`kill`、`status` |
| Nginx | `lnmp nginx <操作>` 或 `/etc/init.d/nginx <操作>` | `start`、`stop`、`reload`、`restart` |
| MySQL | `lnmp mysql <操作>` 或 `/etc/init.d/mysql <操作>` | `start`、`stop`、`restart`、`reload`、`force-reload`、`status` |
| MariaDB | `lnmp mariadb <操作>` 或 `/etc/init.d/mariadb <操作>` | `start`、`stop`、`restart`、`reload`、`force-reload`、`status` |
| PHP-FPM | `lnmp php-fpm <操作>` 或 `/etc/init.d/php-fpm <操作>` | `start`、`stop`、`quit`、`restart`、`reload`、`logrotate` |
| PureFTPd | `lnmp pureftpd <操作>` 或 `/etc/init.d/pure-ftpd <操作>` | `start`、`stop`、`restart`、`kill`、`status` |
| Apache | `lnmp httpd <操作>` 或 `/etc/init.d/httpd <操作>` | `start`、`stop`、`restart`、`graceful`、`graceful-stop`、`configtest`、`status` |

### 启用被禁用的函数

以 root 身份执行以下命令，从默认 PHP 配置的 `disable_functions` 中移除 `system`、`proc_open` 和 `proc_get_status`：

```bash
sed -i 's/,system//g' /usr/local/php/etc/php.ini
sed -i 's/,proc_open//g' /usr/local/php/etc/php.ini
sed -i 's/,proc_get_status//g' /usr/local/php/etc/php.ini
```

修改后，LNMP 模式执行 `lnmp php-fpm restart`；LNMPA、LAMP 模式执行 `lnmp httpd restart`。

### 关闭防跨站

LNMP 模式下，以 root 身份执行以下命令，注释 Nginx FastCGI 配置中的 `PHP_ADMIN_VALUE`：

```bash
sed -i 's/^fastcgi_param PHP_ADMIN_VALUE/#fastcgi_param PHP_ADMIN_VALUE/g' /usr/local/nginx/conf/fastcgi.conf
/usr/local/nginx/sbin/nginx -t && lnmp nginx reload
```

该命令关闭 FastCGI 层设置的 `open_basedir`。如果站点目录中的 `.user.ini` 仍设置了 `open_basedir`，还需移除对应限制；可使用 [tools/remove_open_basedir_restriction.sh](tools/remove_open_basedir_restriction.sh)，按提示输入站点根目录，由脚本处理 `.user.ini`、FastCGI 配置及服务重启。

### 虚拟主机、数据库与 SSL

| 用途 | 命令格式 |
| --- | --- |
| 添加／删除／列出虚拟主机 | `lnmp vhost {add\|del\|list}` |
| 数据库管理 | `lnmp database {add\|list\|edit\|del}` |
| FTP 用户管理 | `lnmp ftp {add\|list\|edit\|del\|show}` |
| 添加 SSL | `lnmp ssl add` |
| 通配符／泛域名 SSL | `lnmp dnsssl {ali\|cf\|dp\|he\|gd\|aws\|namecheap\|namesilo}` |

通配符／泛域名 SSL 需要使用对应服务商的 DNS API。

### 页面入口

将以下地址中的 `yourIP` 替换为服务器 IP；扩展管理页需先安装对应组件。

| 页面 | 地址 |
| --- | --- |
| phpMyAdmin | 随机模式：`https://yourIP/<32位随机字符串>/`；Basic Auth 模式：`https://yourIP/phpmyadmin/` |
| PHP 信息 | `https://yourIP/phpinfo.php` |
| PHP 测试（输出 `hello world`） | `https://yourIP/p.php` |
| XCache | `https://yourIP/xcache/` |
| OPcache | `https://yourIP/ocp.php` |
| APCu | `https://yourIP/apc.php` |

### 默认站点 HTTPS 与 phpMyAdmin 保护

全新安装 LNMP、LNMPA、LAMP 时，会在开始安装前询问 phpMyAdmin 的保护方式：

- **随机路径（默认）**：用安全随机源生成 32 位十六进制字符串作为目录名，不添加 Basic Auth。默认首页不公开入口，安装完成时会显示实际访问地址。
- **Basic Auth**：保留 `/phpmyadmin/`，输入独立用户名、密码并确认密码；该目录下的 PHP 页面和静态资源均受保护。

两种模式都保留 phpMyAdmin 的数据库登录。升级 phpMyAdmin 会保留入口路径、数据库登录配置及 Basic Auth；升级备份保存于 `/usr/local/etc/lnmp/backups/`，不放在网站目录内。旧安装没有安全配置时仍使用 `/phpmyadmin/`。

安装前会探测本机主要 IPv4，允许确认或修改。NAT 环境请填写实际访问的公网 IPv4。默认站点使用绑定该 IP 的自签证书，HTTP 自动 301 跳转至 HTTPS，保留路径和查询参数。浏览器首次访问会提示证书不受信任，需确认信任或自行替换受信任证书。新建虚拟主机继续使用原有配置流程。

安全配置位于 `/usr/local/etc/lnmp/`：

| 文件 | 用途 |
| --- | --- |
| `security.conf` | 已安装的保护模式、入口目录、网站目录和访问 IP，仅 root 可读写 |
| `default.crt` / `default.key` | 自签证书及私钥，RSA 2048 / SHA-256，IP SAN，有效期 365 天；私钥仅 root 可读写 |
| `phpmyadmin.htpasswd` | Basic Auth 密码哈希，root 可读写，www 组可读；不保存明文密码 |

证书不自动续期。到期前可在 root 会话中手动重签，再检查配置并重载服务：

```bash
. ./include/security.sh
. /usr/local/etc/lnmp/security.conf
Default_Server_IP="$Installed_Server_IP"
Create_Default_Certificate
# LNMP / LNMPA
/usr/local/nginx/sbin/nginx -t && /usr/local/nginx/sbin/nginx -s reload
# LAMP 改用
# /usr/local/apache/bin/httpd -t && /usr/local/apache/bin/apachectl graceful
```

无人值守安装可在 `lnmp.conf` 或环境变量中预置 `PhpMyAdmin_Mode=random|basic`、`Default_Server_IP`、`PhpMyAdmin_Auth_User`；Basic Auth 密码通过环境变量 `PhpMyAdmin_Auth_Password` 提供。未预置模式时默认随机路径，未预置 IP 时使用探测结果；Basic Auth 缺少有效凭据或 IP 无效时会报错退出。交互安装的密码隐藏输入，不输出明文密码。

独立安装 Nginx、数据库或多 PHP 版本不应用上述完整安装设置。已有安装不会自动迁移到 HTTPS 或随机路径。

### 卸载

```bash
./uninstall.sh
```

按提示选择卸载 LNMP、LNMPA 或 LAMP。

## 常用路径

### 安装与数据目录

| 组件 | 默认路径 |
| --- | --- |
| Nginx | `/usr/local/nginx/` |
| MySQL | `/usr/local/mysql/` |
| MariaDB | `/usr/local/mariadb/` |
| PHP | `/usr/local/php/` |
| 多 PHP 版本 | `/usr/local/php5.6/`，版本号随实际安装版本变化 |
| PHP 扩展配置 | `/usr/local/php/conf.d/` |
| phpMyAdmin | `/home/wwwroot/default/<32位随机字符串>/` 或 `/home/wwwroot/default/phpmyadmin/` |
| 默认网站根目录 | `/home/wwwroot/default/` |
| Nginx 日志 | `/home/wwwlogs/` |

### 配置文件

| 组件 | 默认配置路径 |
| --- | --- |
| Nginx | `/usr/local/nginx/conf/nginx.conf` |
| MySQL/MariaDB | `/etc/my.cnf` |
| PHP | `/usr/local/php/etc/php.ini` |
| PHP-FPM | `/usr/local/php/etc/php-fpm.conf` |
| PureFTPd | `/usr/local/pureftpd/etc/pure-ftpd.conf` |
| Apache | `/usr/local/apache/conf/httpd.conf` |

## 下载源与 SHA256 评估记录

以下记录来自 2026-10-26 的下载、归档对比和验证，分别保留每批迁移的差异、兼容性结论与验证范围。校验值统一记录在 [src/checksums.sha256](src/checksums.sha256)。

### 基础依赖：五项发布包

以下五项依赖使用固定版本的上游 HTTPS 发布包，并在 [src/checksums.sha256](src/checksums.sha256) 中记录 SHA256。2026-10-26 下载上游包与 soft.lnmp.com 对应包，逐项比较归档目录、文件内容、执行权限及链接，结果如下：

| 依赖 | 上游发布源 | 与 soft.lnmp.com 包的差异 |
| --- | --- | --- |
| libiconv 1.17 | [GNU FTP](https://ftp.gnu.org/gnu/libiconv/) | 压缩包完全一致 |
| libmcrypt 2.5.8 | [项目 SourceForge](https://sourceforge.net/projects/mcrypt/files/Libmcrypt/2.5.8/) | 仅 `config.guess`、`config.sub` 内容不同，LNMP 包使用 2019 年版本 |
| mcrypt 2.6.8 | [项目 SourceForge](https://sourceforge.net/projects/mcrypt/files/MCrypt/2.6.8/) | 仅 `config.guess`、`config.sub` 内容不同；另有普通文件 tar 类型标记差异，不改变内容或执行权限 |
| mhash 0.9.9.9 | [项目 SourceForge](https://sourceforge.net/projects/mhash/files/mhash/0.9.9.9/) | 仅 `config.guess`、`config.sub` 内容不同，LNMP 包使用 2019 年版本 |
| FreeType 2.13.0 | [GNU Savannah](https://download.savannah.gnu.org/releases/freetype/) | 压缩包完全一致 |

五个上游包的顶层目录和 configure 入口均符合现有解压与编译流程，libmcrypt 的 libltdl/configure 也保留。三个旧项目原始的 GNU 配置脚本不能自动识别 aarch64；安装时通过 `Update_GNU_Config`，从已校验的 libiconv 1.17 官方归档中取出 build-aux/config.guess、`config.sub`（分别为 2022、2021 年版本），再运行 configure，以保留架构识别兼容性。SHA256 对应未经修改的上游归档，配置脚本在解压后更新。

在 x86_64、GCC 14.2 环境中，以临时目录作为安装前缀完成了五项依赖的 configure、make、make install 验证，包含 libmcrypt 的 libltdl。libiconv、mhash、FreeType 使用默认编译选项通过；libmcrypt、mcrypt 使用 `CFLAGS='-O2 -std=gnu89'` 通过。libmcrypt 默认选项下的隐式函数声明错误在 LNMP 原包中同样复现，属于原有的 GCC 14 兼容问题，本次换源没有修改编译选项。更新后的 `config.sub` 已检查 x86_64、aarch64、ARM、ppc64le、riscv64，`config.guess` 已模拟 aarch64 检查；这些检查不等同于在各架构实际编译。

迁移前缓存的三个 LNMP 重打包归档与上游 SHA256 不同，校验失败时会删除旧缓存并终止本次安装；重新执行安装会下载相应上游包。

### 编译与兼容依赖：十一项发布包

同日追加迁移以下 11 个发布包，版本及压缩格式保持不变。实际下载上游包和 soft.lnmp.com 对应包后，11 对归档的 SHA256 均完全相同；逐项检查的路径、内容、权限和链接也一致，无需新增源码补丁或架构识别处理。

| 依赖 | 上游 HTTPS 发布源 |
| --- | --- |
| PCRE 8.45 | [项目 SourceForge](https://sourceforge.net/projects/pcre/files/pcre/8.45/) |
| FreeType 2.7 | [GNU Savannah](https://download.savannah.gnu.org/releases/freetype/) |
| jemalloc 5.3.0 | [官方 GitHub Release](https://github.com/jemalloc/jemalloc/releases/tag/5.3.0) |
| gperftools 2.9.1 | [官方 GitHub Release](https://github.com/gperftools/gperftools/releases/tag/gperftools-2.9.1) |
| libunwind 1.2.1 | [GNU Savannah](https://download.savannah.gnu.org/releases/libunwind/) |
| OpenSSL 1.0.2u | [官方历史归档](https://www.openssl.org/source/old/1.0.2/) |
| curl 7.62.0 | [curl 官方下载](https://curl.se/download/) |
| Autoconf 2.13 | [GNU FTP](https://ftp.gnu.org/gnu/autoconf/) |
| ICU4C 58.3 | [官方 GitHub Release](https://github.com/unicode-org/icu/releases/tag/release-58-3) |
| ICU4C 60.3 | [官方 GitHub Release](https://github.com/unicode-org/icu/releases/tag/release-60-3) |
| libzip 1.3.2 | [libzip 官方下载](https://libzip.org/download/) |

除 ICU 的顶层目录为 icu、构建入口为 icu/source/configure 外，其余包均使用原有的“项目名-版本”目录；OpenSSL 使用 config，其余使用 configure。ICU、jemalloc、gperftools 选用正式发布附件，保留现有流程所需的生成文件，未使用 GitHub 自动生成的源码快照。PCRE 的完整安装、单独安装 Nginx 和 Lua 模块下载入口均已更新，其他依赖下载入口也在下载或校验失败时终止。

本批新增 10 条 SHA256，OpenSSL 1.0.2u 复用已存在且与上游相符的条目。已验证 13 处下载调用展开后的地址、失败中止行为、11 个发布包的 SHA256 和构建入口，以及错误缓存的拒绝与删除。归档逐字节一致，换源不会引入源码或目录结构导致的编译差异；本批未逐项重新编译这 11 个依赖，也未执行完整 LNMP 安装，原有编译器与系统依赖要求仍适用。

### Nginx Lua 与 FancyIndex

Lua 和 FancyIndex 的以下六个依赖也使用固定版本的上游 HTTPS 包，并补齐 SHA256。2026-10-26 下载并对比 soft.lnmp.com 对应包后的结果如下：

| 依赖 | 上游发布源 | 与 soft.lnmp.com 包的差异 |
| --- | --- | --- |
| luajit2 2.1-20230119 | [OpenResty 官方标签](https://github.com/openresty/luajit2/releases/tag/v2.1-20230119) | 压缩包逐字节一致 |
| lua-nginx-module 0.10.26 | [OpenResty 官方标签](https://github.com/openresty/lua-nginx-module/releases/tag/v0.10.26) | 压缩包逐字节一致 |
| ngx_devel_kit 0.3.3 | [项目官方标签](https://github.com/vision5/ngx_devel_kit/releases/tag/v0.3.3) | 压缩包逐字节一致 |
| lua-resty-core 0.1.28 | [OpenResty 官方标签](https://github.com/openresty/lua-resty-core/releases/tag/v0.1.28) | 压缩包逐字节一致 |
| lua-resty-lrucache 0.13 | [OpenResty 官方标签](https://github.com/openresty/lua-resty-lrucache/releases/tag/v0.13) | 仅两个 Lua 文件的 _VERSION 不同：上游为 0.13，LNMP 包为 0.11 |
| ngx-fancyindex 0.5.2 | [项目官方发布附件](https://github.com/aperezdc/ngx-fancyindex/releases/tag/v0.5.2) | 压缩包逐字节一致 |

六个上游归档的顶层目录均与现有变量相同，Makefile、Nginx 模块 config 入口、文件权限和链接保持一致。lrucache 的差异仅涉及 lib/resty/lrucache.lua、lib/resty/lrucache/pureffi.lua 的版本字符串，其余代码完全一致；使用上游的 0.13 标识，不复制 LNMP 包中的 0.11 标识。现有解压、LuaJIT 编译、Resty 库安装和 Nginx --add-module 路径均无需调整。

已验证六处下载地址和失败中止行为、SHA256、错误缓存拒绝与删除，并在 x86_64、GCC 14.2 环境的临时目录中完成 LuaJIT 编译安装、两个 Resty 库的 make install，确认文件位于 PREFIX/lib/lua。使用 LuaJIT 和模拟的 ngx.now 加载 lrucache 两种实现，检查版本为 0.13，并完成 set/get/delete 操作。未执行完整 Nginx 模块编译或运行集成测试；本次变更不增加目录结构或 C 源码差异。

旧 LNMP lrucache 归档无法通过上游 SHA256，校验失败时会删除旧缓存并终止；重新执行安装会下载上游原包。

### Swoole

Swoole 的六个现有版本改用 PECL 官方 HTTPS 固定版本包，并在 [src/checksums.sha256](src/checksums.sha256) 中补齐 SHA256。2026-10-26 实际下载、对比结果如下：

| 组件版本 | 可信源 | 与 soft.lnmp.com 对应包的比较 |
| --- | --- | --- |
| Swoole 6.0.2 | [PECL 官方发布包](https://pecl.php.net/get/swoole-6.0.2.tgz) | SHA256、路径、内容、权限和链接一致 |
| Swoole 4.8.13 | [PECL 官方发布包](https://pecl.php.net/get/swoole-4.8.13.tgz) | 旧源返回 HTTP 404，无法进行双源比较；PECL 包的目录和 `config.m4` 入口符合现有流程 |
| Swoole 4.5.11 | [PECL 官方发布包](https://pecl.php.net/get/swoole-4.5.11.tgz) | SHA256、路径、内容、权限和链接一致 |
| Swoole 4.3.6 | [PECL 官方发布包](https://pecl.php.net/get/swoole-4.3.6.tgz) | SHA256、路径、内容、权限和链接一致 |
| Swoole 1.10.5 | [PECL 官方发布包](https://pecl.php.net/get/swoole-1.10.5.tgz) | SHA256、路径、内容、权限和链接一致 |
| Swoole 1.6.10 | [PECL 官方发布包](https://pecl.php.net/get/swoole-1.6.10.tgz) | SHA256、路径、内容、权限和链接一致 |

六个 PECL 包均包含 `swoole-<版本>/` 源码目录及顶层 `package.xml`，源码目录内保留 `config.m4`，适配现有 `Tar_Cd`、`phpize` 和 configure 流程。五个可比较的包逐字节一致，换源不会引入结构或源码差异；4.8.13 仅验证了官方包的结构，无法确认旧源是否存在补丁。六处下载均在下载或校验失败时立即终止，避免继续解压、编译。

已验证 PHP 版本分支的下载地址、实际解压路径、六项 SHA256，以及错误缓存的拒绝和删除；本批未实际编译扩展或执行完整安装。

原有版本选择仍有独立限制：6.0.2 的 `package.xml` 要求 PHP >= 8.1，而脚本仍将 PHP 8.0 指向它，且未覆盖 PHP 8.4/8.5；这些问题不是本次换源造成的。

### PHP 8 扩展与依赖：七项发布包

PHP 8 扩展安装涉及的以下七个归档改用上游 HTTPS 固定版本包，并在 [src/checksums.sha256](src/checksums.sha256) 中补齐 SHA256。2026-10-26 实际下载上游包与 soft.lnmp.com 对应包，七对压缩包逐字节一致；另逐项比较归档成员的路径、类型、文件内容、权限和链接，均一致。

| 组件版本 | 上游发布源 | 与 soft.lnmp.com 包的差异 |
| --- | --- | --- |
| APCu 5.1.22 | [PECL 官方发布包](https://pecl.php.net/get/apcu-5.1.22.tgz) | 无，SHA256 一致 |
| Memcached 服务端 1.6.39 | [官方发布包](https://www.memcached.org/files/memcached-1.6.39.tar.gz) | 无，SHA256 一致 |
| PHP memcache 8.2 | [PECL 官方发布包](https://pecl.php.net/get/memcache-8.2.tgz) | 无，SHA256 一致 |
| libmemcached 1.0.18 | [项目 Launchpad 发布包](https://launchpad.net/libmemcached/1.0/1.0.18/+download/libmemcached-1.0.18.tar.gz) | 无，SHA256 一致 |
| PHP memcached 3.2.0 | [PECL 官方发布包](https://pecl.php.net/get/memcached-3.2.0.tgz) | 无，SHA256 一致 |
| ImageMagick 7.1.1-8 | [官方发布包](https://download.imagemagick.org/archive/releases/ImageMagick-7.1.1-8.tar.xz) | 无，SHA256 一致 |
| Imagick 3.7.0 | [PECL 官方发布包](https://pecl.php.net/get/imagick-3.7.0.tgz) | 无，SHA256 一致 |

四个 PECL 包均保留顶层 `package.xml` 和原有的组件名-版本源码目录，目录内包含 `config.m4`，适配现有 `Tar_Cd`、`phpize` 和 configure 流程；APCu 的 `apc.php` 也保留。三个独立组件均保留原有顶层目录、可执行的 configure 和 `Makefile.in`，使用正式发布归档，无需额外运行 `autoreconf`。libmemcached 原有 GCC 7 兼容补丁已通过 `patch --dry-run` 检查。七个归档本身完全相同，换源不会引入目录结构、源码、权限或链接差异导致的编译问题，无需新增源码补丁。

七处下载均在下载或 SHA256 校验失败时立即终止，避免继续解压、编译。

已验证 PHP 8.0/8.3/8.4/8.5 分支的七项下载地址、文件名、解压目标和失败中止行为，以及七项官方归档的 SHA256、有效缓存复用、错误缓存的拒绝和删除。本批未实际编译扩展或执行完整安装，既有 PHP 版本、编译器和系统依赖兼容限制仍适用。

共享的 APCu 5.1.22、Memcached 服务端、libmemcached、ImageMagick 和 Imagick 下载分支在其他 PHP 版本下也使用相同上游源；其他旧版归档、SourceGuardian 和 IonCube 不在本次迁移范围内。

### SourceGuardian 历史加载器

SourceGuardian 按要求保持原安装脚本和 soft.lnmp.com 下载地址，不升级，也不新增未经上游核验的 SHA256。官网 [加载器下载页](https://www.sourceguardian.com/loaders.html) 当前提供 17.0.0；本次未找到现有 12.1.2、14.0.0、14.0.3 的可用官方历史下载地址，因此无法对这些旧包作同版本双源一致性判断。

旧源可获取的五个包为 14.0.0 x86_64、12.1.2 i386/aarch64、14.0.3 armhf/aarch64，包内 version 均与路径一致，`ixed.*.lin` 均位于 ZIP 根目录，ELF 架构也与下载分支相符，可沿用 `unzip -d loaders.linux-${ARCH}` 后复制 Loader 的路径。

SourceGuardian 是预编译 Loader，没有源码编译步骤；本次未执行 PHP 加载测试。12.1.2 armhf 的旧源地址已返回 HTTP 404，该原有下载问题仍存在。

另对比了官网下载的 17.0.0 x86_64/armhf/aarch64 包：Loader 同样位于 ZIP 根目录，但与旧包同名的二进制内容均不同，新增 PHP 8.3–8.5 Loader；x86_64 包还移除了 PHP 4.3–5.2 Loader，i386 当前官网下载地址返回 HTTP 404。因此不能将官网当前包当作现有历史包的同版本替换。
