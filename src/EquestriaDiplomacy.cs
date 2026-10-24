using System.IO;
using System.Linq;
using System.Reflection;
using System.Xml;
using TaleWorlds.CampaignSystem;
using TaleWorlds.CampaignSystem.Actions;
using TaleWorlds.CampaignSystem.CampaignBehaviors;

namespace EquestriaMod
{
    // Дипломатия на старте кампании: войны, союзы, торговые соглашения и перемирия с данью.
    //
    // Без этого все державы начинают в мире со всеми, и первые войны игра придумывает сама через
    // недели. Игра из XML стойки держав не читает, поэтому tools/make_world.py пишет свой файл
    // ModuleData/equestria_diplomacy.xml (из world_data.DIPLOMACY), а это поведение применяет его
    // один раз при создании новой кампании. Дальше всё живёт в сохранении, как и ванильные войны.
    //
    // Союзы и торговля — штатные механики War Sails: заключаются через поведения игры
    // (AllianceCampaignBehavior, TradeAgreementsCampaignBehavior), отдельных действий у них нет.
    // Дань — это мир после войны: объявляем войну и тут же заключаем мир с выплатой.
    public class EquestriaDiplomacyBehavior : CampaignBehaviorBase
    {
        private const string FileName = "equestria_diplomacy.xml";
        private const int TributeDays = 100;

        public override void RegisterEvents()
        {
            // После того как игра доделала свой новый мир (в том числе завела списки союзов и
            // соглашений): раньше поведения союзов ещё не готовы принимать записи.
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
                        // перемирие с данью: a платит b — это мир после войны, поэтому сначала война
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
