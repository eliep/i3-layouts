FROM python:3.7-buster

RUN echo force-unsafe-io > /etc/dpkg/dpkg.cfg.d/docker-apt-speedup

RUN echo 'deb http://http.us.debian.org/debian/ testing non-free contrib main' >> /etc/apt/sources.list
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get -t testing install -y \
    gcc-8-base \
    i3-wm \
    xvfb \
    xdotool \
    -o APT::Immediate-Configure=0

WORKDIR /usr/src

COPY requirements.txt ./
RUN pip install flake8 pytest python-xlib
RUN pip install --no-cache-dir -r requirements.txt
