# Apache Tika offline resource

Place the approved Apache Tika application JAR here as `tika-app.jar` before the AArch64 release build.

The application uses it only through a local `java -jar ... --text` process to extract legacy `.doc` text. It never starts a server and never sends document data over the network. If the JAR or a local Java runtime is unavailable, WordVault falls back to an installed `antiword` or `catdoc` executable and otherwise records `DOC_PARSER_UNAVAILABLE`.

The release operator must record the Tika version, upstream URL, SHA-256 and license notice in the release manifest.

