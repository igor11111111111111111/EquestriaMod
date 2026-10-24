<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Убираем ванильные королевства: и лишние, и те, чьи культуры мы заняли (наши заведены под своими id). -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <xsl:template match="Kingdom[@id='empire_w']"/>
  <xsl:template match="Kingdom[@id='empire_s']"/>
  <xsl:template match="Kingdom[@id='battania']"/>
  <xsl:template match="Kingdom[@id='empire']"/>
  <xsl:template match="Kingdom[@id='empire']"/>
  <xsl:template match="Kingdom[@id='empire']"/>
  <xsl:template match="Kingdom[@id='empire']"/>
  <xsl:template match="Kingdom[@id='vlandia']"/>
  <xsl:template match="Kingdom[@id='battania']"/>
  <xsl:template match="Kingdom[@id='nord']"/>
  <xsl:template match="Kingdom[@id='sturgia']"/>
  <xsl:template match="Kingdom[@id='khuzait']"/>
  <xsl:template match="Kingdom[@id='aserai']"/>
</xsl:stylesheet>
