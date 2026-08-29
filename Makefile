MKDIR?=mkdir
RM?=rm
SED?=sed
INSTALL?=install
PREFIX?=/opt/pipx/venvs/director
MANDIR?=${PREFIX}/share/man
PIPX_INSTALL_FLAGS=
OVERLORD_VERSION_SUFFIX?=

.if defined(SYSTEM_SITE_PACKAGES)
PIPX_INSTALL_FLAGS+=--system-site-packages
.endif

.if !defined(NOEDITABLE)
PIPX_INSTALL_FLAGS+=-e
.endif

all: install-director install-manpages

install-director:
.if defined(OVERLORD_VERSION_SUFFIX) && !empty(OVERLORD_VERSION_SUFFIX)
	env OVERLORD_VERSION_SUFFIX=${OVERLORD_VERSION_SUFFIX} pipx install ${PIPX_INSTALL_FLAGS} --force --global .
.else
	pipx install ${PIPX_INSTALL_FLAGS} --force --global .
.endif

install-manpages:
	${MKDIR} -m 755 -p "${DESTDIR}${MANDIR}/man1"
	${MKDIR} -m 755 -p "${DESTDIR}${MANDIR}/man5"

	${INSTALL} -m 444 director.1 "${DESTDIR}${MANDIR}/man1/director.1"
	${INSTALL} -m 444 director-spec.5 "${DESTDIR}${MANDIR}/man5/director-spec.5"

uninstall: uninstall-director uninstall-manpages

uninstall-director:
	pipx uninstall --global director

uninstall-manpages:
	${RM} -f "${DESTDIR}${MANDIR}/man1/director.1"
	${RM} -f "${DESTDIR}${MANDIR}/man5/director-spec.5"

