## [Unreleased]

- PR#164 (no sha yet)
  - rs232.SerialData doesn't hide exceptions during opening of the port.
  - Support added for testing of serial devices.

- PR#148 (a436f2a127af43b6655410321f820d7660a0fe51)
  - Remove threading support from rs232.SerialData, it wasn't used.

## [0.5.1] - 2017-12-02
### Added
- First real release!
- Working POCS features:
    + mount (iOptron)
    + cameras (DSLR, SBIG)
    + focuer (Birger)
    + scheduler (simple)
- Relies on separate repositories PEAS and PACE
- Automated testing with travis-ci.org
- Code coverage via codecov.io
- Basic install scripts
