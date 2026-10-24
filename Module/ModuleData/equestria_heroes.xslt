<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Удаляем всех ванильных героев, кроме main_hero (герой игрока) — их знатные кланы тоже удалены. -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <xsl:template match="Hero[@id!='main_hero']"/>
</xsl:stylesheet>
