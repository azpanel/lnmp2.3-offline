#!/usr/bin/env bash
export PATH=$PATH:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin

# Check if user is root
if [ "$(id -u)" != "0" ]; then
    echo "Error: You must be root to run this script!"
    exit 1
fi

echo "+-------------------------------------------------------------------+"
echo "|   Reset MySQL/MariaDB root Password for LNMP, Written by Licess   |"
echo "+-------------------------------------------------------------------+"
echo "|       A tool to reset MySQL/MariaDB root password for LNMP        |"
echo "+-------------------------------------------------------------------+"
echo "|       For more information please visit https://lnmp.org          |"
echo "+-------------------------------------------------------------------+"
echo "|           Usage: ./reset_mysql_root_password.sh                   |"
echo "+-------------------------------------------------------------------+"

if [ -x /usr/local/mariadb/bin/mariadb ] || [ -x /usr/local/mariadb/bin/mysql ]; then
    DB_Name="mariadb"
elif [ -x /usr/local/mysql/bin/mysql ]; then
    DB_Name="mysql"
else
    echo "MySQL/MariaDB not found!"
    exit 1
fi

DB_Bin="/usr/local/${DB_Name}/bin"
DB_Client="${DB_Bin}/mysql"
DB_Admin="${DB_Bin}/mysqladmin"
DB_Safe="${DB_Bin}/mysqld_safe"
DB_Service="/etc/init.d/${DB_Name}"
if [ "${DB_Name}" = "mariadb" ]; then
    [ -x "${DB_Bin}/mariadb" ] && DB_Client="${DB_Bin}/mariadb"
    [ -x "${DB_Bin}/mariadb-admin" ] && DB_Admin="${DB_Bin}/mariadb-admin"
    [ -x "${DB_Bin}/mariadbd-safe" ] && DB_Safe="${DB_Bin}/mariadbd-safe"
else
    DB_Ver=$("${DB_Bin}/mysql_config" --version) || exit 1
    if [[ "${DB_Ver}" =~ ^([0-9]+)\.([0-9]+)\. ]]; then
        DB_Major=${BASH_REMATCH[1]}
        DB_Minor=${BASH_REMATCH[2]}
    else
        echo "Error: Cannot determine MySQL version: ${DB_Ver}"
        exit 1
    fi
fi

for DB_Command in "${DB_Client}" "${DB_Admin}" "${DB_Safe}" "${DB_Service}"; do
    if [ ! -x "${DB_Command}" ]; then
        echo "Error: Required command not found: ${DB_Command}"
        exit 1
    fi
done

while :;do
    DB_Root_Password=""
    if ! IFS= read -r -s -p "Enter New ${DB_Name} root password: " DB_Root_Password; then
        echo
        exit 1
    fi
    echo
    if [ "${DB_Root_Password}" = "" ]; then
        echo "Error: Password can't be NULL!!"
    else
        break
    fi
done

# Use SQL-standard quote escaping, with backslash escapes disabled below.
DB_SQL_Password=${DB_Root_Password//\'/\'\'}

echo "Stopping ${DB_Name}..."
if ! "${DB_Service}" stop; then
    echo "Error: Could not stop ${DB_Name}."
    exit 1
fi
# A previous failed reset may have left a server outside systemd's control.
if "${DB_Admin}" --protocol=socket --user=root --password= --connect-timeout=2 ping >/dev/null 2>&1; then
    if ! SYSTEMCTL_SKIP_REDIRECT=1 "${DB_Service}" stop; then
        echo "Error: Could not stop the existing ${DB_Name} process."
        exit 1
    fi
fi

Restore_DB_Service()
{
    local reset_status=$?
    trap - EXIT HUP INT TERM
    # The recovery server was started directly, so bypass systemd redirection.
    # The init script uses the PID file and handles both mysqld and mariadbd.
    if ! SYSTEMCTL_SKIP_REDIRECT=1 "${DB_Service}" stop; then
        if kill -0 "${DB_Safe_PID}" 2>/dev/null; then
            echo "Error: Could not stop the recovery server; check ${DB_Name} manually."
            exit 1
        fi
    fi
    wait "${DB_Safe_PID}" 2>/dev/null
    echo "Restarting the actual ${DB_Name} service"
    if ! "${DB_Service}" start; then
        echo "Error: Could not restart ${DB_Name}."
        exit 1
    fi
    if [ "${reset_status}" -eq 0 ]; then
        echo "Password successfully reset for 'root'@'localhost'."
    fi
    exit "${reset_status}"
}

echo "Starting ${DB_Name} with skip grant tables"
"${DB_Safe}" --skip-grant-tables --skip-networking >/dev/null 2>&1 &
DB_Safe_PID=$!
trap Restore_DB_Service EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

DB_Ready=0
for ((attempt = 0; attempt < 60; attempt++)); do
    if ! kill -0 "${DB_Safe_PID}" 2>/dev/null; then
        break
    fi
    if "${DB_Client}" --protocol=socket --user=root --password= --connect-timeout=2 --execute='SELECT 1' >/dev/null 2>&1; then
        DB_Ready=1
        break
    fi
    sleep 1
done
if [ "${DB_Ready}" -ne 1 ]; then
    echo "Error: ${DB_Name} recovery server did not become ready."
    exit 1
fi

# MariaDB supports SET PASSWORD across versions, including the mysql.user
# view introduced in 10.4, and preserves unix_socket authentication.
DB_Password_SQL="SET PASSWORD FOR 'root'@'localhost' = PASSWORD('${DB_SQL_Password}');"
if [ "${DB_Name}" = "mysql" ] && ((DB_Major > 5 || (DB_Major == 5 && DB_Minor >= 7))); then
    DB_Password_SQL="ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_SQL_Password}';"
fi

echo "Updating ${DB_Name} root password..."
if ! "${DB_Client}" --protocol=socket --user=root --password= --connect-timeout=5 << EOF
SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES';
FLUSH PRIVILEGES;
${DB_Password_SQL}
EOF
then
    echo "Reset ${DB_Name} root password failed!"
    exit 1
fi
exit 0
