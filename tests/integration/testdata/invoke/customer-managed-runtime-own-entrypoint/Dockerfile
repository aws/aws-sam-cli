# A customer-managed runtime image that starts only from its own ENTRYPOINT: it has no /var/runtime/bootstrap.
FROM public.ecr.aws/lambda/python:3.13

# Lambda runs a customer-managed runtime's ENTRYPOINT with the function handler as its only argument.
RUN printf '#!/bin/sh\nexport _HANDLER="$1"\nexec /var/lang/bin/python3.13 /var/runtime/bootstrap.py\n' \
        > /usr/local/bin/my-entrypoint \
    && chmod 755 /usr/local/bin/my-entrypoint \
    && rm /var/runtime/bootstrap

ENTRYPOINT ["/usr/local/bin/my-entrypoint"]
