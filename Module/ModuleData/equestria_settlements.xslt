<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Удаляем все ванильные поселения, кроме логовищ разбойников и скита отшельника. -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <xsl:template match="Settlement[not(Components/Hideout) and @id!='retirement_retreat']"/>
</xsl:stylesheet>
