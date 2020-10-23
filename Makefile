DISTRO := $(shell lsb_release -si | tr A-Z a-z)
DISTRO_MAJOR_VERSION := $(shell lsb_release -sr | cut -d. -f1)
DISTRO_NAME := $(shell lsb_release -sc | tr A-Z a-z)
VERSION := $(shell head -n 1 debian-common/changelog | awk '{match( $$0, /\(.+?\)/); print substr( $$0, RSTART+1, RLENGTH-2 ) }' | cut -d- -f1 )

all:
	./setup.py build

install:
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/var/lib/config-curator/templates/nullunit/
	install -m 755 bin/nullunitIterate $(DESTDIR)/usr/bin
	install -m 755 bin/nullunitInterface $(DESTDIR)/usr/bin
	install -m 755 bin/nullunitAddPackageFile $(DESTDIR)/usr/bin
	install -m 644 templates/nullunit/* $(DESTDIR)/var/lib/config-curator/templates/nullunit

ifeq (ubuntu, $(DISTRO))
	./setup.py install --root=$(DESTDIR) --install-purelib=/usr/lib/python3/dist-packages/ --prefix=/usr --no-compile -O0
else
	./setup.py install --root=$(DESTDIR) --prefix=/usr --no-compile -O0
endif

version:
	echo $(VERSION)

clean:
	./setup.py clean || true
	$(RM) -fr build
	$(RM) -f dpkg
	$(RM) -f rpm
	$(RM) -r htmlcov
ifeq (ubuntu, $(DISTRO))
	dh_clean || true
endif

dist-clean: clean
	$(RM) -fr debian
	$(RM) -fr rpmbuild
	$(RM) -f dpkg-setup
	$(RM) -f rpm-setup

.PHONY:: all install version clean dist-clean

test-blueprints:
	echo ubuntu-xenial-base

test-requires:
	echo flake8 python3-cinp python3-dev python3-pytest python3-pytest-cov

lint:
	flake8 --ignore=E501,E201,E202,E111,E126,E114,E402,W605 --statistics .

test:
	py.test-3 nullunit --cov=nullunit --cov-report html --cov-report term

.PHONY:: test-blueprints test-requires lint test

dpkg-blueprints:
	echo ubuntu-trusty-base ubuntu-xenial-base ubuntu-bionic-base ubuntu-focal-base

dpkg-requires:
	echo dpkg-dev debhelper python3-dev python3-setuptools dh-python

dpkg-setup:
	./debian-setup
	touch dpkg-setup

dpkg:
	dpkg-buildpackage -b -us -uc
	touch dpkg

dpkg-file:
	echo $(shell ls ../nullunit_*.deb)

.PHONY:: dpkg-blueprints dpkg-requires dpkg-file

rpm-blueprints:
	echo centos-6-base centos-7-base

rpm-requires:
	echo rpm-build
ifeq (6, $(DISTRO_MAJOR_VERSION))
	echo python34-setuptools
else
	echo python36-setuptools
endif

rpm-setup:
	./rpmbuild-setup
	touch rpm-setup

rpm:
	rpmbuild -v -bb rpmbuild/config.spec
	touch rpm

rpm-file:
	echo $(shell ls rpmbuild/RPMS/*/nullunit-*.rpm)

.PHONY:: rpm-blueprints rpm-requires rpm-file

auto-builds:
	echo installcheck

installcheck-depends:
	echo nullunit:dev

installcheck-resources:
	echo trusty:{ \"resource_name\": \"ubuntu-trusty-small\" }
	echo xenail:{ \"resource_name\": \"ubuntu-xenial-small\" }
	echo bionic:{ \"resource_name\": \"ubuntu-bionic-small\" }
	echo centos6:{ \"resource_name\": \"centos-6-small\" }
	echo centos7:{ \"resource_name\": \"centos-7-small\" }

installcheck:
ifeq (ubuntu, $(DISTRO))
	apt install -y nullunit
else
	yum install -y nullunit
endif
	touch installcheck

.PHONY:: auto-builds installcheck-depends installcheck-resources
