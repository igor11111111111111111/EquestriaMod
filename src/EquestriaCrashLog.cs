using System;
using System.IO;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Text;

namespace EquestriaMod
{
    // Writes .NET exceptions to a separate file next to the mod.
    //
    // Why: on a crash the game calls its own native handler, and the managed stack never reaches the
    // log — rgl_log breaks off mid-word, and the dump shows only clr.dll frames instead of the crash site.
    // The first-chance hook fires before all of that, while the stack is still intact.
    //
    // File: <mod folder>\eq_exceptions.log, overwritten on every game launch.
    //
    // Verbose mode (10.10.2026, before release): ordinary lines (Log) and catching EVERY first-chance
    // exception in the whole game (with a stack capture) — only with the /eqverbose switch, which
    // run.ps1 adds on any test launch. For the player (launch from the launcher) the log gets only stage
    // marks (Note), warnings (Warn, including Try step errors) and unhandled exceptions.
    public static class EquestriaCrashLog
    {
        private const long SizeLimit = 8 * 1024 * 1024;

        /// <summary>Verbose log: the /eqverbose switch on the game's command line.</summary>
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
                // The library is in <mod>\bin\Win64_Shipping_Client — go up two levels.
                string bin = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                string root = Path.GetFullPath(Path.Combine(bin, "..", ".."));
                _path = Path.Combine(root, "eq_exceptions.log");
                // With a BOM: without it Notepad and PowerShell read Russian text as mojibake.
                File.WriteAllText(_path, "Запуск игры " + DateTime.Now.ToString("dd.MM.yyyy HH:mm:ss") + "\r\n",
                    new UTF8Encoding(true));

                // The first-chance hook is expensive: it fires on any exception in the game, including
                // ones the game handles itself, and captures the stack every time — verbose mode only.
                if (Verbose)
                {
                    AppDomain.CurrentDomain.FirstChanceException += OnFirstChance;
                }
                AppDomain.CurrentDomain.UnhandledException += OnUnhandled;
            }
            catch (Exception)
            {
                // Nowhere to write — stay silent, otherwise the log would break the game launch.
            }
        }

        // A mark for a mod step: shows exactly where the next exception happened.
        public static void Note(string text)
        {
            Append("--- " + text);
        }

        // An ordinary log line: numbers, found objects, check results.
        public static void Log(string text)
        {
            if (Verbose)
            {
                Append(text);
            }
        }

        // A visible warning: something was not found or looks wrong, but the game is still alive.
        public static void Warn(string text)
        {
            Append("!!! " + text);
        }

        // Wrapper for a risky step. An exception inside does not crash the launch, but goes to the log
        // together with the step name — without it the game's native handler shows only "crashed somewhere".
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
            // For a first-chance exception the StackTrace property holds only the method that threw it:
            // the stack is filled in during unwinding, which has not started yet. So we capture the
            // current thread stack separately — it shows WHO called the failing method.
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
                // Append and close the file: on a crash the last entry must not be lost.
                File.AppendAllText(_path, line, new UTF8Encoding(true));
                _written += line.Length;
            }
            catch (Exception)
            {
            }
        }
    }
}
