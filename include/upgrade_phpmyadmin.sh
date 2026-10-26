#!/usr/bin/env bash

Upgrade_phpMyAdmin()
{
    Load_PhpMyAdmin_Location || exit 1
    local phpmyadmin_path="${Default_Website_Dir}/${PhpMyAdmin_Dir}"
    local staging_dir backup_dir cookie_secret
    phpMyAdmin_Version=""
    echo "You can get version number from https://www.phpmyadmin.net/downloads/"
    read -r -p "Please enter phpMyAdmin version you want, (example: 5.2.3): " phpMyAdmin_Version || exit 1
    if [[ ! "${phpMyAdmin_Version}" =~ ^[0-9]+(\.[0-9]+){1,3}([.-][a-zA-Z0-9]+)*$ ]]; then
        echo "Error: You must enter a valid phpMyAdmin version!!"
        exit 1
    fi
    echo "+---------------------------------------------------------+"
    echo "|   You will upgrade phpMyAdmin version to ${phpMyAdmin_Version}"
    echo "+---------------------------------------------------------+"

    Press_Start

    echo "============================check files=================================="
    cd "${cur_dir}/src" || exit 1
    if [ -s "phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz" ]; then
        echo "phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz [found]"
    else
        echo "Notice: phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz not found!!!download now......"
        if wget -c --progress=dot:giga "https://files.phpmyadmin.net/phpMyAdmin/${phpMyAdmin_Version}/phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz"; then
            echo "Download phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz successfully!"
        else
            echo "You enter phpMyAdmin Version was: ${phpMyAdmin_Version}"
            Echo_Red "Error! You entered a wrong version number, please check!"
            sleep 5
            exit 1
        fi
    fi
    Verify_Download_File "phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz" || exit 1
    echo "============================check files=================================="
    case "$(readlink -m "${LNMP_Security_Dir}")/" in
        "$(readlink -m "${Default_Website_Dir}")/"*)
            Security_Error "Upgrade backups must be outside the default document root."
            exit 1 ;;
    esac
    staging_dir=$(mktemp -d "${cur_dir}/src/.phpmyadmin-upgrade.XXXXXX") || exit 1
    local new_path="${staging_dir}/phpMyAdmin-${phpMyAdmin_Version}-all-languages"
    echo "Uncompress phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz ..."
    if ! tar Jxf "phpMyAdmin-${phpMyAdmin_Version}-all-languages.tar.xz" -C "${staging_dir}"; then
        rm -rf "${staging_dir}"
        exit 1
    fi
    if [ -f "${phpmyadmin_path}/config.inc.php" ]; then
        \cp "${phpmyadmin_path}/config.inc.php" "${new_path}/config.inc.php" || { rm -rf "${staging_dir}"; exit 1; }
    else
        \cp "${cur_dir}/conf/config.inc.php" "${new_path}/config.inc.php" || { rm -rf "${staging_dir}"; exit 1; }
        cookie_secret=$(openssl rand -hex 16) || { rm -rf "${staging_dir}"; exit 1; }
        sed -i "s/LNMPORG/${cookie_secret}/g" "${new_path}/config.inc.php" || { rm -rf "${staging_dir}"; exit 1; }
    fi
    if ! { mkdir -p "${new_path}/upload" "${new_path}/save" && chmod -R 755 "${new_path}" && chown -R www:www "${new_path}"; }; then
        rm -rf "${staging_dir}"
        exit 1
    fi
    mkdir -p "${LNMP_Security_Dir}/backups" && chmod 700 "${LNMP_Security_Dir}/backups" || { rm -rf "${staging_dir}"; exit 1; }
    backup_dir=$(mktemp -d "${LNMP_Security_Dir}/backups/phpmyadmin-${Upgrade_Date}.XXXXXX") || { rm -rf "${staging_dir}"; exit 1; }
    echo "Backup old phpMyAdmin to ${backup_dir}/phpmyadmin..."
    mv "${phpmyadmin_path}" "${backup_dir}/phpmyadmin" || { rm -rf "${staging_dir}"; exit 1; }
    if ! mv "${new_path}" "${phpmyadmin_path}"; then
        mv "${backup_dir}/phpmyadmin" "${phpmyadmin_path}"
        rm -rf "${staging_dir}"
        Security_Error "Unable to install new phpMyAdmin; restored previous directory."
        exit 1
    fi
    rm -rf "${staging_dir}"
    Echo_Green "======== upgrade phpMyAdmin completed ======"
}
