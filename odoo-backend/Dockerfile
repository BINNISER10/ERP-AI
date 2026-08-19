FROM odoo:18.0

USER root

# Install Python packages required by custom addons.
RUN pip install --no-cache-dir \
    stripe \
    && rm -rf /root/.cache/pip

USER odoo
