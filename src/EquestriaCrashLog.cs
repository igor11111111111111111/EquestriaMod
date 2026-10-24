using System;
using System.IO;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Text;

namespace EquestriaMod
{
    // Запись исключений .NET в отдельный файл рядом с модом.
    //
    // Зачем: игра при падении зовёт свой родной обработчик, и управляемый стек до журнала не
    // доходит — в rgl_log обрыв на полуслове, а в дампе вместо места падения только кадры clr.dll.
    // Перехват первого шанса срабатывает раньше всего этого, пока стек ещё цел.
    //
    // Файл: <папка мода>\eq_exceptions.log, переписывается при каждом запуске игры.
    //
    // Подробный режим (10.10.2026, перед релизом): обычные строки (Log) и перехват КАЖДОГО исключения
    // «первого шанса» во всей игре (со снятием стека) — только с ключом /eqverbose, его добавляет
    // run.ps1 при любом тестовом запуске. У игрока (запуск из лаунчера) в журнал идут лишь отметки
    // этапов (Note), предупреждения (Warn, в том числе ошибки шагов Try) и необработанные исключения.
    public static class EquestriaCrashLog
    {
        private const long SizeLimit = 8 * 1024 * 1024;

        /// <summary>Подробный журнал: ключ /eqverbose в командной строке игры.</summary>
        public static readonly bool Verbose = Array.Exists(Environment.GetCommandLineArgs(),
            a => string.Equals(a, "/eqverbose", StringComparison.OrdinalIgnoreCase));

        private static string _path;
        private static bool _installed;
        private static long _written;

        public static void Install()
        {
            if (_installed)
            {
                return;
            }
            _installed = true;
            try
            {
                // Библиотека лежит в <мод>\bin\Win64_Shipping_Client — поднимаемся на два уровня.
                string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                string root = Path.GetFullPath(Path.Combine(bin, "..", ".."));
                _path = Path.Combine(root, "eq_exceptions.log");
                // С меткой BOM: без неё блокнот и PowerShell читают русский текст крякозябрами.
                File.WriteAllText(_path, "Запуск игры " + DateTime.Now.ToString("dd.MM.yyyy HH:mm:ss") + "\r\n",
                    new UTF8Encoding(true));

                // Перехват первого шанса дорогой: срабатывает на любое исключение в игре, в том числе
                // обработанное ею самой, и каждый раз снимает стек — только в подробном режиме.
                if (Verbose)
                {
                    AppDomain.CurrentDomain.FirstChanceException += OnFirstChance;
                }
                AppDomain.CurrentDomain.UnhandledException += OnUnhandled;
            }
            catch (Exception)
            {
                // Некуда писать — молчим, иначе сломаем запуск игры из-за журнала.
            }
        }

        // Отметка о шаге мода: видно, на чём именно случилось следующее исключение.
        public static void Note(string text)
        {
            Append("--- " + text);
        }

        // Обычная строка journal: числа, найденные объекты, результаты проверок.
        public static void Log(string text)
        {
            if (Verbose)
            {
                Append(text);
            }
        }

        // Заметное предупреждение: что-то не найдено или выглядит неправильно, но игра ещё жива.
        public static void Warn(string text)
        {
            Append("!!! " + text);
        }

        // Обёртка для опасного шага. Исключение внутри не роняет запуск, но попадает в журнал
        // вместе с именем шага — без неё в родном обработчике игры видно только «упало где-то».
        public static void Try(string step, Action action)
        {
            try
            {
                action();
            }
            catch (Exception e)
            {
                Warn("шаг «" + step + "» не выполнен: " + e.GetType().Name + ": " + e.Message
                    + "\r\n" + e.StackTrace);
            }
        }

        private static void OnFirstChance(object sender, FirstChanceExceptionEventArgs e)
        {
            // У исключения «первого шанса» свойство StackTrace содержит только метод, который его
            // бросил: стек дописывается по мере раскрутки, а она ещё не началась. Поэтому снимаем
            // текущий стек потока отдельно — из него видно, КТО вызвал упавший метод.
            string callers;
            try
            {
                callers = new System.Diagnostics.StackTrace(2, true).ToString();
            }
            catch (Exception)
            {
                callers = "(стек вызовов снять не удалось)";
            }
            Append(Describe("исключение", e.Exception) + "\r\n  вызвано отсюда:\r\n" + callers);
        }

        private static void OnUnhandled(object sender, UnhandledExceptionEventArgs e)
        {
            Append(Describe("НЕОБРАБОТАННОЕ", e.ExceptionObject as Exception));
        }

        private static string Describe(string kind, Exception e)
        {
            if (e == null)
            {
                return kind + ": объект исключения пуст";
            }
            string text = kind + ": " + e.GetType().FullName + ": " + e.Message + "\r\n" + e.StackTrace;
            if (e.InnerException != null)
            {
                text += "\r\n  вложенное: " + e.InnerException.GetType().FullName
                    + ": " + e.InnerException.Message + "\r\n" + e.InnerException.StackTrace;
            }
            return text;
        }

        private static void Append(string text)
        {
            if (_path == null || _written > SizeLimit)
            {
                return;
            }
            try
            {
                string line = "[" + DateTime.Now.ToString("HH:mm:ss.fff") + "] " + text + "\r\n";
                // Дописываем с закрытием файла: при падении последняя запись не должна потеряться.
                File.AppendAllText(_path, line, new UTF8Encoding(true));
                _written += line.Length;
            }
            catch (Exception)
            {
            }
        }
    }
}
