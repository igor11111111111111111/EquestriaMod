<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Все персонажи игры становятся пони: людей в Эквусе нет.
       Своя раса — по культуре (RACE_BY_CULTURE в tools/make_world.py). -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <xsl:template match="NPCCharacter">
    <xsl:copy>
      <xsl:apply-templates select="@*[name()!='race']"/>
      <xsl:attribute name="race">
        <xsl:choose>
          <xsl:when test="@culture='Culture.aserai'">changeling</xsl:when>
          <xsl:when test="@culture='Culture.battania'">hippogriff</xsl:when>
          <xsl:when test="@culture='Culture.khuzait'">yak</xsl:when>
          <xsl:when test="@culture='Culture.nord'">deer</xsl:when>
          <xsl:when test="@culture='Culture.sturgia'">dragon</xsl:when>
          <xsl:when test="@culture='Culture.vlandia'">griffon</xsl:when>
          <xsl:otherwise>pony</xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
