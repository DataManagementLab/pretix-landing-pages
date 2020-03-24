FROM pretix/standalone:stable
USER root
COPY . /pretix-landing-pages
RUN export PYTHONPATH=$PYTHONPATH:/pretix/src && \
    cd /pretix-landing-pages && \
    # pip install -r requirements.txt && \
    pip install .

USER pretixuser
RUN cd /pretix/src && make production
