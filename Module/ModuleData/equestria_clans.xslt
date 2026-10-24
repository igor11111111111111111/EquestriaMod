<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Удаляем все ванильные знатные кланы (у них есть super_faction). Разбойничьи и наёмничьи кланы сохраняются. -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <xsl:template match="Faction[@super_faction]"/>
</xsl:stylesheet>
