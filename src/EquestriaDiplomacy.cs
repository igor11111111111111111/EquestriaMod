using System.IO;
using System.Linq;
using System.Reflection;
using System.Xml;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.CampaignBehaviors;

namespace EquestriaMod
{
    // Diplomacy at campaign start: wars, alliances, trade agreements and truces with tribute.
    //
    // Without this all kingdoms start at peace with everyone, and the game invents the first wars by itself
    // weeks later. The game does not read kingdom stances from XML, so tools/make_world.py writes its own file
    // ModuleData/equestria_diplomacy.xml (from world_data.DIPLOMACY), and this behavior applies it
    // once when a new campaign is created. After that everything lives in the save, like vanilla wars.
    //
    // Alliances and trade are standard War Sails mechanics: they are made through the game's behaviors
    // (AllianceCampaignBehavior, TradeAgreementsCampaignBehavior), they have no separate actions.
    // Tribute is peace after a war: we declare war and immediately make peace with payment.
    public class EquestriaDiplomacyBehavior : CampaignBehaviorBase
    {
        private const string FileName = "equestria_diplomacy.xml";
        private const int TributeDays = 100;

        public override void RegisterEvents()
        {
            // After the game has finished its new world (including setting up the lists of alliances and
            // agreements): earlier the alliance behaviors are not ready to accept entries yet.
            CampaignEvents.OnNewGameCreatedPartialFollowUpEndEvent.AddNonSerializedListener(this, _ =>
                EquestriaCrashLog.Try("дипломатия на старте", Apply));
        }

        public override void SyncData(IDataStore dataStore)
        {
        }

        private static void Apply()
        {
            string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string path = Path.GetFullPath(Path.Combine(bin, "..", "..", "ModuleData", FileName));
            if (!File.Exists(path))
            {
                EquestriaCrashLog.Warn("дипломатия: нет файла " + path);
                return;
            }
            var alliances = Campaign.Current.GetCampaignBehavior<AllianceCampaignBehavior>();
            var trade = Campaign.Current.GetCampaignBehavior<TradeAgreementsCampaignBehavior>();

            var document = new XmlDocument();
            document.Load(path);
            int wars = 0, unions = 0, trades = 0, tributes = 0;
            foreach (XmlElement node in document.GetElementsByTagName("Stance"))
            {
                string kind = node.GetAttribute("kind");
                Kingdom a = Kingdom.All.FirstOrDefault(k => k.StringId == node.GetAttribute("a"));
                Kingdom b = Kingdom.All.FirstOrDefault(k => k.StringId == node.GetAttribute("b"));
                if (a == null || b == null || a == b)
                {
                    EquestriaCrashLog.Warn($"дипломатия: нет державы {node.GetAttribute("a")} или {node.GetAttribute("b")}");
                    continue;
                }
                switch (kind)
                {
                    case "war":
                        DeclareWarAction.ApplyByDefault(a, b);
                        wars++;
                        break;
                    case "alliance":
                        if (alliances == null)
                        {
                            EquestriaCrashLog.Warn("дипломатия: в игре нет поведения союзов — союз пропущен");
                            break;
                        }
                        alliances.StartAlliance(a, b);
                        unions++;
                        break;
                    case "trade":
                        if (trade == null)
                        {
                            EquestriaCrashLog.Warn("дипломатия: в игре нет поведения торговых соглашений — пропущено");
                            break;
                        }
                        trade.MakeTradeAgreement(a, b, CampaignTime.Days(365f));
                        trades++;
                        break;
                    case "tribute":
                        int gold = int.TryParse(node.GetAttribute("gold"), out int g) ? g : 100;
                        // truce with tribute: a pays b - this is peace after a war, so first war
                        DeclareWarAction.ApplyByDefault(a, b);
                        MakePeaceAction.ApplyByKingdomDecision(a, b, gold, TributeDays);
                        tributes++;
                        break;
                    default:
                        EquestriaCrashLog.Warn("дипломатия: неизвестный вид " + kind);
                        break;
                }
            }
            EquestriaCrashLog.Log($"дипломатия на старте: войн {wars}, союзов {unions}, "
                + $"торговых соглашений {trades}, перемирий с данью {tributes}");
        }
    }
}
