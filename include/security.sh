#!/usr/bin/env bash

# Kept outside the document root so upgrades can recover the selected entry point.
LNMP_Security_Dir=${LNMP_Security_Dir:-/usr/local/etc/lnmp}

Security_Error()
{
    echo "Error: $*" >&2
    return 1
}

Valid_Server_IP()
{
    local part
    local -a parts
    [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    IFS=. read -r -a parts <<< "$1"
    for part in "${parts[@]}"; do
        [[ "$part" = 0 || "$part" != 0* ]] || return 1
        (( 10#$part <= 255 )) || return 1
    done
    [[ "$1" != 0.0.0.0 && "$1" != 255.255.255.255 ]]
}

Default_Security_Selection()
{
    local detected_ip confirmation
    echo "phpMyAdmin protection (database login is required in both modes):"
    echo "1: Random 32-character path, without Basic Auth (Default)"
    echo "2: /phpmyadmin/ with Basic Auth"
    while :; do
        if [ -z "${PhpMyAdmin_Mode}" ]; then
            if [ -n "${LNMP_Auto}" ]; then
                PhpMyAdmin_Mode=random
            else
                read -r -p "Choose protection [1]: " PhpMyAdmin_Mode || return 1
                PhpMyAdmin_Mode=${PhpMyAdmin_Mode:-random}
            fi
        fi
        case "${PhpMyAdmin_Mode}" in
            1|random) PhpMyAdmin_Mode=random; break ;;
            2|basic) PhpMyAdmin_Mode=basic; break ;;
            *)
                Security_Error "Choose 1 (random) or 2 (basic)."
                [ -n "${LNMP_Auto}" ] && return 1
                PhpMyAdmin_Mode=
                ;;
        esac
    done

    if [ "${PhpMyAdmin_Mode}" = basic ]; then
        while [[ ! "${PhpMyAdmin_Auth_User}" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$ ]]; do
            [ -n "${LNMP_Auto}" ] && { Security_Error "Set a valid PhpMyAdmin_Auth_User for Basic Auth."; return 1; }
            read -r -p "Basic Auth username (letters, digits, _, . or -): " PhpMyAdmin_Auth_User || return 1
        done
        while :; do
            if [ -z "${PhpMyAdmin_Auth_Password}" ]; then
                [ -n "${LNMP_Auto}" ] && { Security_Error "Set PhpMyAdmin_Auth_Password for Basic Auth."; return 1; }
                read -r -s -p "Basic Auth password: " PhpMyAdmin_Auth_Password || return 1
                echo
                read -r -s -p "Confirm Basic Auth password: " confirmation || return 1
                echo
                if [ "${PhpMyAdmin_Auth_Password}" != "${confirmation}" ]; then
                    echo "Passwords do not match."
                    PhpMyAdmin_Auth_Password=
                    continue
                fi
            fi
            if [[ -n "${PhpMyAdmin_Auth_Password}" && "${PhpMyAdmin_Auth_Password}" != *$'\n'* && "${PhpMyAdmin_Auth_Password}" != *$'\r'* ]]; then
                break
            fi
            Security_Error "Basic Auth password must be nonempty and contain no line breaks."
            [ -n "${LNMP_Auto}" ] && return 1
            PhpMyAdmin_Auth_Password=
        done
        PhpMyAdmin_Dir=phpmyadmin
    fi

    if [ -z "${Default_Server_IP}" ]; then
        detected_ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<NF;i++) if ($i=="src") {print $(i+1); exit}}')
        if ! Valid_Server_IP "${detected_ip}"; then
            detected_ip=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i ~ /^[0-9]+\./) {print $i; exit}}')
        fi
        if [ -n "${LNMP_Auto}" ]; then
            Default_Server_IP=${detected_ip}
        else
            echo "Use the public access IPv4 if this server is behind NAT."
            read -r -p "Default site / certificate IPv4 [${detected_ip}]: " Default_Server_IP || return 1
            Default_Server_IP=${Default_Server_IP:-${detected_ip}}
        fi
    fi
    until Valid_Server_IP "${Default_Server_IP}"; do
        Security_Error "A valid access IPv4 is required."
        [ -n "${LNMP_Auto}" ] && return 1
        read -r -p "Default site / certificate IPv4: " Default_Server_IP || return 1
    done
    echo "Default site: https://${Default_Server_IP}/ (HTTP redirects to HTTPS)."
    echo "The self-signed certificate will require browser trust confirmation."
}

Prepare_Default_Security()
{
    # Called after dependencies are installed, before the application is extracted.
    local website_path security_path password_hash
    website_path=$(readlink -m "${Default_Website_Dir}") || return 1
    security_path=$(readlink -m "${LNMP_Security_Dir}") || return 1
    case "${security_path}/" in
        "${website_path}/"*) Security_Error "Security files must be outside the default document root."; return 1 ;;
    esac
    mkdir -p "${LNMP_Security_Dir}" || return 1
    chown root:www "${LNMP_Security_Dir}" && chmod 750 "${LNMP_Security_Dir}" || return 1
    if [ "${PhpMyAdmin_Mode}" = random ]; then
        PhpMyAdmin_Dir=$(openssl rand -hex 16) || return 1
        [[ "${PhpMyAdmin_Dir}" =~ ^[a-f0-9]{32}$ ]] || return 1
        [ ! -e "${Default_Website_Dir}/${PhpMyAdmin_Dir}" ] || { Security_Error "Random phpMyAdmin directory already exists."; return 1; }
    elif [ "${PhpMyAdmin_Mode}" = basic ]; then
        # APR1 is supported by both Nginx and the legacy Apache 2.2 option.
        password_hash=$(printf '%s\n' "${PhpMyAdmin_Auth_Password}" | openssl passwd -apr1 -stdin) || return 1
        (umask 077; printf '%s:%s\n' "${PhpMyAdmin_Auth_User}" "${password_hash}" > "${LNMP_Security_Dir}/phpmyadmin.htpasswd") || return 1
        unset PhpMyAdmin_Auth_Password
        chown root:www "${LNMP_Security_Dir}/phpmyadmin.htpasswd" && chmod 640 "${LNMP_Security_Dir}/phpmyadmin.htpasswd" || return 1
    else
        Security_Error "phpMyAdmin protection has not been selected."
        return 1
    fi
}

Create_Default_Certificate()
{
    # An OpenSSL config file also works with versions predating req -addext.
    (
        umask 077
        cat > "${LNMP_Security_Dir}/openssl.cnf" <<EOF || return 1
[req]
distinguished_name = dn
x509_extensions = extensions
prompt = no
[dn]
CN = ${Default_Server_IP}
[extensions]
subjectAltName = IP:${Default_Server_IP}
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
EOF
        openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days 365 \
            -config "${LNMP_Security_Dir}/openssl.cnf" \
            -keyout "${LNMP_Security_Dir}/default.key" \
            -out "${LNMP_Security_Dir}/default.crt"
    ) || return 1
    chmod 600 "${LNMP_Security_Dir}/default.key" || return 1
    rm -f "${LNMP_Security_Dir}/openssl.cnf"
}

Configure_Default_Nginx()
{
    local config_dir=${1:-/usr/local/nginx/conf}
    cat > "${config_dir}/default-security.conf" <<EOF || return 1
        ssl_certificate "${LNMP_Security_Dir}/default.crt";
        ssl_certificate_key "${LNMP_Security_Dir}/default.key";
        ssl_protocols TLSv1.2 TLSv1.3;
EOF
    if [ "${PhpMyAdmin_Mode}" = basic ]; then
        cat >> "${config_dir}/default-security.conf" <<EOF || return 1
        location = /phpmyadmin { return 301 https://\$host/phpmyadmin/\$is_args\$args; }
        location ^~ /phpmyadmin/ {
            auth_basic "phpMyAdmin";
            auth_basic_user_file "${LNMP_Security_Dir}/phpmyadmin.htpasswd";
            location ~ /\. { deny all; }
EOF
        if [ "${Stack}" = lnmp ]; then
            echo '            include enable-php.conf;' >> "${config_dir}/default-security.conf" || return 1
        else
            cat >> "${config_dir}/default-security.conf" <<'EOF' || return 1
            proxy_pass http://127.0.0.1:88;
            include proxy.conf;
EOF
        fi
        echo '        }' >> "${config_dir}/default-security.conf" || return 1
    fi
    cat > "${config_dir}/default-http.conf" <<'EOF' || return 1
server {
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}
EOF
    # Retain the existing default server's PHP, Lua, logging and root settings.
    sed -i '/listen 80 default_server/s/80 default_server/443 ssl default_server/; /listen 443 ssl default_server/a\        include default-security.conf;' "${config_dir}/nginx.conf" || return 1
    sed -i '/^include vhost\/\*.conf;/i\include default-http.conf;' "${config_dir}/nginx.conf"
}

Configure_Default_Apache()
{
    local config_dir=${1:-/usr/local/apache/conf}
    local access_rule='Require all granted'
    [ "${ApacheSelect}" = 1 ] && access_rule=$'Order allow,deny\n    Allow from all'
    sed -i 's|^#Include conf/extra/httpd-ssl.conf|Include conf/extra/httpd-ssl.conf|' "${config_dir}/httpd.conf" || return 1
    # The default vhost must remain first for both ports (before conf/vhost/*).
    cat > "${config_dir}/extra/httpd-vhosts.conf" <<EOF || return 1
<VirtualHost *:80>
    ServerName ${Default_Server_IP}
    RewriteEngine On
    RewriteRule ^ https://${Default_Server_IP}%{REQUEST_URI} [R=301,L,NE]
</VirtualHost>
<VirtualHost *:443>
    ServerName ${Default_Server_IP}
    DocumentRoot "${Default_Website_Dir}"
    SSLEngine on
    SSLProtocol all -SSLv2 -SSLv3 -TLSv1 -TLSv1.1
    SSLStrictSNIVHostCheck off
    SSLCertificateFile "${LNMP_Security_Dir}/default.crt"
    SSLCertificateKeyFile "${LNMP_Security_Dir}/default.key"
    ErrorLog "/home/wwwlogs/IP-error_log"
    CustomLog "/home/wwwlogs/IP-access_log" combined
    <Directory "${Default_Website_Dir}">
        Options FollowSymLinks
        AllowOverride All
        ${access_rule}
        DirectoryIndex index.html index.php
        SetOutputFilter DEFLATE
    </Directory>
EOF
    if [ "${PhpMyAdmin_Mode}" = basic ]; then
        cat >> "${config_dir}/extra/httpd-vhosts.conf" <<EOF || return 1
    <Directory "${Default_Website_Dir}/phpmyadmin">
        AllowOverride None
        AuthType Basic
        AuthName "phpMyAdmin"
        AuthUserFile "${LNMP_Security_Dir}/phpmyadmin.htpasswd"
        Require valid-user
    </Directory>
EOF
    fi
    echo '</VirtualHost>' >> "${config_dir}/extra/httpd-vhosts.conf" || return 1
    if [ "${ApacheSelect}" = 1 ]; then
        sed -i '1i\NameVirtualHost *:80' "${config_dir}/extra/httpd-vhosts.conf" || return 1
    fi
}

Save_Default_Security()
{
    (
        umask 077
        {
            printf 'Installed_PhpMyAdmin_Mode=%q\n' "${PhpMyAdmin_Mode}"
            printf 'Installed_PhpMyAdmin_Dir=%q\n' "${PhpMyAdmin_Dir}"
            printf 'Installed_Website_Dir=%q\n' "${Default_Website_Dir}"
            printf 'Installed_Server_IP=%q\n' "${Default_Server_IP}"
        } > "${LNMP_Security_Dir}/security.conf"
    ) || return 1
    chmod 600 "${LNMP_Security_Dir}/security.conf"
}

Configure_Default_Security()
{
    Create_Default_Certificate || return 1
    if [ "${Stack}" = lamp ]; then
        Configure_Default_Apache /usr/local/apache/conf && /usr/local/apache/bin/httpd -t || return 1
    else
        Configure_Default_Nginx /usr/local/nginx/conf && /usr/local/nginx/sbin/nginx -t || return 1
        if [ "${Stack}" = lnmpa ]; then
            /usr/local/apache/bin/httpd -t || return 1
        fi
    fi
    Save_Default_Security
}

Load_PhpMyAdmin_Location()
{
    if [ -f "${LNMP_Security_Dir}/security.conf" ]; then
        . "${LNMP_Security_Dir}/security.conf" || return 1
        [[ "${Installed_PhpMyAdmin_Dir}" = phpmyadmin || "${Installed_PhpMyAdmin_Dir}" =~ ^[a-f0-9]{32}$ ]] || { Security_Error "Invalid saved phpMyAdmin directory."; return 1; }
        [[ "${Installed_Website_Dir}" = /* && "${Installed_Website_Dir}" != / ]] || return 1
        PhpMyAdmin_Dir=${Installed_PhpMyAdmin_Dir}
        Default_Website_Dir=${Installed_Website_Dir}
    else
        PhpMyAdmin_Dir=phpmyadmin
    fi
    [ -d "${Default_Website_Dir}/${PhpMyAdmin_Dir}" ] || { Security_Error "Installed phpMyAdmin directory not found."; return 1; }
}
