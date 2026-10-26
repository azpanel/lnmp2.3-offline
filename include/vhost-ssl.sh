#!/usr/bin/env bash

# Read local configuration/certificates only; listing must not require network or services.
VHost_SSL_Config_Entries()
{
    LC_ALL=C awk -v kind="$2" '
    function token() { if (word != "") args[++count] = word; word = "" }
    function directive(    name) {
        token()
        name = tolower(args[1])
        if (count >= 2) {
            if ((kind == "nginx" && name == "ssl_certificate") ||
                (kind == "apache" && name == "sslcertificatefile"))
                print "cert\t" args[2]
            else if (name == "include" || (kind == "apache" && name == "includeoptional"))
                print name "\t" args[2]
        }
        delete args
        count = 0
    }
    {
        for (i = 1; i <= length($0); i++) {
            ch = substr($0, i, 1)
            if (escaped) { word = word ch; escaped = 0; continue }
            if (ch == "\\") { escaped = 1; continue }
            if (quote != "") {
                if (ch == quote) quote = ""
                else word = word ch
                continue
            }
            if (ch == "\"" || ch == "\047") { quote = ch; continue }
            if (ch == "#") break
            if (ch ~ /[ \t\r]/) { token(); continue }
            if (kind == "nginx" && ch == ";") { directive(); continue }
            if (kind == "nginx" && (ch == "{" || ch == "}")) {
                word = ""; delete args; count = 0; continue
            }
            word = word ch
        }
        if (quote == "") {
            token()
            if (kind == "apache") directive()
        }
    }
    ' "$1"
}

VHost_SSL_Certificate_Paths()
{
    local config=$1 kind=$2 base=$3 depth=${4:-0}
    local entry value included found
    if [ "${depth}" -ge 12 ]; then
        printf 'error\tConfiguration include loop/depth limit\n'
        return
    fi
    if [ ! -r "${config}" ]; then
        printf 'error\tConfiguration unreadable\n'
        return
    fi
    while IFS=$'\t' read -r entry value; do
        if [[ "${value}" == *'$'* ]]; then
            printf 'error\tDynamic certificate/include path\n'
            continue
        fi
        [[ "${value}" = /* ]] || value="${base}/${value}"
        if [ "${entry}" = cert ]; then
            printf 'cert\t%s\n' "${value}"
        else
            found=n
            while IFS= read -r included; do
                [ -f "${included}" ] || continue
                found=y
                VHost_SSL_Certificate_Paths "${included}" "${kind}" "${base}" "$((depth + 1))"
            done < <(compgen -G "${value}")
            if [[ "${found}" = n && "${entry}" != includeoptional ]]; then
                printf 'error\tConfiguration include missing\n'
            fi
        fi
    done < <(VHost_SSL_Config_Entries "${config}" "${kind}")
}

VHost_SSL_Certificate_Row()
{
    local name=$1 certificate=$2 now=$3
    local metadata issuer before after begin end remaining days status color=37
    if [ ! -r "${certificate}" ]; then
        printf '37\t%s\t-\t-\t-\tCertificate missing/unreadable\n' "${name}"
        return
    fi
    if ! command -v openssl >/dev/null 2>&1; then
        printf '37\t%s\t-\t-\t-\tOpenSSL unavailable\n' "${name}"
        return
    fi
    if ! metadata=$(LC_ALL=C openssl x509 -in "${certificate}" -noout -issuer -dates \
        -nameopt sep_multiline,sname,utf8,esc_ctrl 2>/dev/null); then
        printf '37\t%s\t-\t-\t-\tInvalid certificate\n' "${name}"
        return
    fi
    issuer=$(printf '%s\n' "${metadata}" | awk '
        /^issuer=/ { in_issuer = 1; next }
        /^not(Before|After)=/ { in_issuer = 0 }
        in_issuer && /^[ \t]+[^=]+=/ {
            line = $0; sub(/^[ \t]+/, "", line)
            full_issuer = full_issuer (full_issuer == "" ? "" : ", ") line
        }
        /^[ \t]*O[ \t]*=/ { sub(/^[ \t]*O[ \t]*=[ \t]*/, ""); organization = $0 }
        /^[ \t]*CN[ \t]*=/ { sub(/^[ \t]*CN[ \t]*=[ \t]*/, ""); common_name = $0 }
        END {
            if (organization != "" && common_name != "") print organization " / " common_name
            else if (organization != "") print organization
            else if (common_name != "") print common_name
            else if (full_issuer != "") print full_issuer
            else print "Unknown issuer"
        }')
    before=$(printf '%s\n' "${metadata}" | sed -n 's/^notBefore=//p')
    after=$(printf '%s\n' "${metadata}" | sed -n 's/^notAfter=//p')
    if [ -z "${before}" ] || [ -z "${after}" ] ||
       ! begin=$(LC_ALL=C date -u -d "${before}" +%s 2>/dev/null) ||
       ! end=$(LC_ALL=C date -u -d "${after}" +%s 2>/dev/null); then
        printf '37\t%s\t%s\t-\t-\tInvalid certificate dates\n' "${name}" "${issuer}"
        return
    fi
    before=$(date -u -d "@${begin}" '+%Y-%m-%d %H:%M:%S')
    after=$(date -u -d "@${end}" '+%Y-%m-%d %H:%M:%S')
    remaining=$((end - now))
    days=$((remaining / 86400))
    if [ "${remaining}" -le 0 ]; then
        days=$(( -remaining / 86400 ))
        status="Expired ${days} days ago"
        [ "${days}" -eq 0 ] && status='Expired <1 day ago'
        [ "${days}" -eq 1 ] && status='Expired 1 day ago'
    elif [ "${days}" -ge 31 ]; then
        color=32; status="${days} days"
    elif [ "${days}" -ge 14 ]; then
        color=33; status="${days} days"
    elif [ "${days}" -ge 1 ]; then
        color=31; status="${days} days"
    else
        status='<1 day'
    fi
    [ "${remaining}" -gt 0 ] && [ "${days}" -eq 1 ] && status='1 day'
    if [ "${begin}" -gt "${now}" ]; then
        color=37; status="Not valid yet; ${days} days to expiry"
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${color}" "${name}" "${issuer}" "${before}" "${after}" "${status}"
}

List_VHost_SSL()
{
    local kind=$1 directory=$2 base=$3
    local config name entry value found now use_color=n
    now=$(date +%s) || return 1
    if [ -z "${NO_COLOR:-}" ] &&
       { [ "${FORCE_COLOR:-0}" = 1 ] || { [ -t 1 ] && [ "${TERM:-}" != dumb ]; }; }; then
        use_color=y
    fi
    {
        printf '0\tVirtualhost\tIssuer\tNot Before (UTC)\tNot After (UTC)\tExpires In\n'
        if [ ! -d "${directory}" ]; then
            printf '37\t-\t-\t-\t-\tVirtualhost directory missing\n'
        else
            for config in "${directory}"/*.conf; do
                [ -f "${config}" ] || continue
                name=${config##*/}; name=${name%.conf}
                found=n
                while IFS=$'\t' read -r entry value; do
                    found=y
                    if [ "${entry}" = cert ]; then
                        VHost_SSL_Certificate_Row "${name}" "${value}" "${now}"
                    else
                        printf '37\t%s\t-\t-\t-\t%s\n' "${name}" "${value}"
                    fi
                done < <(VHost_SSL_Certificate_Paths "${config}" "${kind}" "${base}" | awk '!seen[$0]++')
                if [ "${found}" = n ]; then
                    printf '37\t%s\t-\t-\t-\tNo SSL\n' "${name}"
                fi
            done
        fi
    } | awk -F '\t' -v color="${use_color}" '
        {
            for (i = 1; i <= NF; i++) cells[NR, i] = $i
            for (i = 2; i <= 6; i++) if (length($i) > width[i]) width[i] = length($i)
        }
        END {
            for (row = 1; row <= NR; row++) {
                if (color == "y" && row > 1) printf "\033[%sm", cells[row, 1]
                for (i = 2; i <= 6; i++) {
                    printf "%-*s", width[i], cells[row, i]
                    if (i < 6) printf " | "
                }
                if (color == "y" && row > 1) printf "\033[0m"
                printf "\n"
            }
        }'
}
