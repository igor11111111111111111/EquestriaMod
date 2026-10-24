<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <!-- Ездовых зверей в Эквусе нет: все летают на свитках (src/EquestriaFlightScroll.cs).
       Боевые кони и верблюды ванили остаются в игре как предметы (ссылки из чужих войск и
       сейвов не ломаются), но перестают быть товаром: не лежат в лавках, не идут призами и
       в караваны. Вьючные (sumpter_horse, mule, pack_camel) становятся «повозками»: меш
       телеги вместо зверя (bd_cart_a — единственный меш телеги в ванили), название — через локализацию (tools/make_items.py,
       те же строковые id, что у ванили). Грузоподъёмность и прочее не трогаем. 10.10.2026. -->
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
  </xsl:template>
  <!-- вьючные → повозки -->
  <xsl:template match="Item[@id='sumpter_horse' or @id='mule' or @id='pack_camel']">
    <xsl:copy>
      <xsl:apply-templates select="@*[name()!='mesh']"/>
      <xsl:attribute name="mesh">bd_cart_a</xsl:attribute>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>
  <!-- Повозки — не ездовые (10.10.2026): их нельзя надеть в слот коня, только возить в обозе.
       Вьючными остаются (is_pack_animal), поэтому грузоподъёмность отряду дают как прежде; скотом
       (на мясо) не становятся — скот у движка = не ездовой И не вьючный. -->
  <xsl:template match="Item[@id='sumpter_horse' or @id='mule' or @id='pack_camel']/ItemComponent/Horse/@is_mountable">
    <xsl:attribute name="is_mountable">false</xsl:attribute>
  </xsl:template>
  <!-- упряжь (сбруя, сёдла: Type="HorseHarness") — не товар -->
  <xsl:template match="Item[@Type='HorseHarness' and not(starts-with(@id,'eq_'))]">
    <xsl:copy>
      <xsl:apply-templates select="@*[name()!='is_merchandise']"/>
      <xsl:attribute name="is_merchandise">false</xsl:attribute>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>
  <!-- остальные звери с компонентом Horse — не товар -->
  <xsl:template match="Item[ItemComponent/Horse and not(@id='sumpter_horse' or @id='mule' or @id='pack_camel') and not(starts-with(@id,'eq_'))]">
    <xsl:copy>
      <xsl:apply-templates select="@*[name()!='is_merchandise']"/>
      <xsl:attribute name="is_merchandise">false</xsl:attribute>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
