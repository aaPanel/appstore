FROM hyperf/hyperf:8.3-alpine-v3.19-swoole-slim

LABEL maintainer="ThinkCMF" version="1.1.0" license="MIT" app.name="ThinkCMF"

##
# ---------- env settings ----------
##
# --build-arg timezone=Asia/Shanghai
ARG timezone

ENV TZ=${timezone:-"Asia/Shanghai"} 
ENV PHP_BUILD_VERSION=83

# update
RUN set -ex \
    # show php version and extensions
    && php -v \
    && php -m \
    && php --ri swoole \
    #  ---------- some config ----------
    && cd /etc/php${PHP_BUILD_VERSION} \
    # - config PHP
    && sed -i "s/;curl.cainfo =/curl.cainfo=\/etc\/ssl\/certs\/ca-certificates.crt/g" /etc/php${PHP_BUILD_VERSION}/php.ini \
    && sed -i "s/;openssl.cafile=/openssl.cafile=\/etc\/ssl\/certs\/ca-certificates.crt/g" /etc/php${PHP_BUILD_VERSION}/php.ini \
    && { \
        echo "upload_max_filesize=128M"; \
        echo "post_max_size=128M"; \
        echo "memory_limit=1G"; \
        echo "date.timezone=${TZ}"; \
    } | tee conf.d/99_overrides.ini \
    # - config composer
    && composer config -g repo.packagist composer https://mirrors.aliyun.com/composer/ \
    # - config timezone
    && ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo "${TZ}" > /etc/timezone \
    # ---------- clear works ----------
    && rm -rf /var/cache/apk/* /tmp/* /usr/share/man \
    && echo -e "\033[42;37m Build Completed :).\033[0m\n"