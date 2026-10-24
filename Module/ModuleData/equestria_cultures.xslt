<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Вырезаем ванильные списки имён у наших культур — иначе рядом с пони остались бы кальрадийцы. -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <xsl:template match="Culture[@id='empire']/male_names"/>
  <xsl:template match="Culture[@id='empire']/female_names"/>
  <xsl:template match="Culture[@id='empire']/clan_names"/>
  <xsl:template match="Culture[@id='aserai']/male_names"/>
  <xsl:template match="Culture[@id='aserai']/female_names"/>
  <xsl:template match="Culture[@id='aserai']/clan_names"/>
  <xsl:template match="Culture[@id='vlandia']/*"/>
  <xsl:template match="Culture[@id='khuzait']/*"/>
  <xsl:template match="Culture[@id='sturgia']/*"/>
  <xsl:template match="Culture[@id='nord']/*"/>
  <xsl:template match="Culture[@id='battania']/*"/>
</xsl:stylesheet>
