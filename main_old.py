from dublib.Methods import Cls, CheckPythonMinimalVersion, MakeRootDirectories, ReadJSON, Shutdown
from dublib.WebRequestor import Protocols, WebConfig, WebLibs, WebRequestor
from dublib.CLI.Terminalyzer import ArgumentsTypes, Command, Terminalyzer
from Source.Functions import SecondsToTimeString
from Source.Collector import Collector
from Source.Parser import Parser

import datetime
import logging
import time
import sys
import os

#==========================================================================================#
# >>>>> ИНИЦИАЛИЗАЦИЯ СКРИПТА <<<<< #
#==========================================================================================#

# Проверка поддержки используемой версии Python.
CheckPythonMinimalVersion(3, 10)
# Создание папок в корневой директории.
MakeRootDirectories(["Logs"])

#==========================================================================================#
# >>>>> НАСТРОЙКА ЛОГГИРОВАНИЯ <<<<< #
#==========================================================================================#

# Получение текущей даты.
CurrentDate = datetime.datetime.now()
# Время запуска скрипта.
StartTime = time.time()
# Формирование пути к файлу лога.
LogFilename = "Logs/" + str(CurrentDate)[:-7] + ".log"
LogFilename = LogFilename.replace(":", "-")
# Установка конфигнурации.
logging.basicConfig(filename = LogFilename, encoding = "utf-8", level = logging.INFO, format = "%(asctime)s %(levelname)s: %(message)s", datefmt = "%Y-%m-%d %H:%M:%S")
# Отключение части сообщений логов библиотеки requests.
logging.getLogger("requests").setLevel(logging.CRITICAL)
# Отключение части сообщений логов библиотеки urllib3.
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
# Отключение части сообщений логов библиотеки httpx.
logging.getLogger("httpx").setLevel(logging.CRITICAL)

#==========================================================================================#
# >>>>> ЧТЕНИЕ НАСТРОЕК <<<<< #
#==========================================================================================#

# Запись в лог сообщения: заголовок подготовки скрипта к работе.
logging.info("====== Preparing to starting ======")
# Запись в лог используемой версии Python.
logging.info("Starting with Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro) + " on " + str(sys.platform) + ".")
# Запись команды, использовавшейся для запуска скрипта.
logging.info("Launch command: \"" + " ".join(sys.argv[1:len(sys.argv)]) + "\".")
# Очистка консоли.
Cls()
# Чтение настроек.
Settings = ReadJSON("Settings.json")

# Форматирование путей.
if Settings["covers-directory"] == "": Settings["covers-directory"] = "Covers"
if Settings["images-directory"] == "": Settings["images-directory"] = "Images"
if Settings["novels-directory"] == "": Settings["novels-directory"] = "Novels"
Settings["covers-directory"] = Settings["covers-directory"].rstrip("\\/")
Settings["images-directory"] = Settings["images-directory"].rstrip("\\/")
Settings["novels-directory"] = Settings["novels-directory"].rstrip("\\/")

#==========================================================================================#
# >>>>> НАСТРОЙКА ОБРАБОТЧИКА КОМАНД <<<<< #
#==========================================================================================#

# Список описаний обрабатываемых команд.
CommandsList = list()

# Создание команды: collect.
COM_collect = Command("collect")
COM_collect.add_flag_position(["f"])
COM_collect.add_flag_position(["s"])
COM_collect.add_key_position(["filters"], ArgumentsTypes.All)
CommandsList.append(COM_collect)

# Создание команды: getcov.
COM_getcov = Command("getcov")
COM_getcov.add_argument(ArgumentsTypes.All, important = True)
COM_getcov.add_flag_position(["f"])
COM_getcov.add_flag_position(["s"])
CommandsList.append(COM_getcov)

# Создание команды: parse.
COM_parse = Command("parse")
COM_parse.add_argument(ArgumentsTypes.All, important = True, layout_index = 1)
COM_parse.add_flag_position(["collection", "local"], important = True, layout_index = 1)
COM_parse.add_flag_position(["h", "y"])
COM_parse.add_flag_position(["f"])
COM_parse.add_flag_position(["s"])
COM_parse.add_key_position(["from"], ArgumentsTypes.All)
CommandsList.append(COM_parse)

# Создание команды: repair.
COM_repair = Command("repair")
COM_repair.add_argument(ArgumentsTypes.All, important = True)
COM_repair.add_flag_position(["s"])
COM_repair.add_key_position(["chapter"], ArgumentsTypes.Number, important = True)
CommandsList.append(COM_repair)

# Создание команды: update.
COM_update = Command("update")
COM_update.add_flag_position(["f"])
COM_update.add_flag_position(["s"])
COM_update.add_key_position(["hours"], ArgumentsTypes.Number)
COM_update.add_key_position(["from"], ArgumentsTypes.All)
CommandsList.append(COM_update)

# Инициализация обработчика консольных аргументов.
CAC = Terminalyzer()
# Получение информации о проверке команд.
CommandDataStruct = CAC.check_commands(CommandsList)

# Если не удалось определить команду.
if CommandDataStruct == None:
	# Запись в лог критической ошибки: неверная команда.
	logging.critical("Unknown command.")
	# Завершение работы скрипта с кодом ошибки.
	exit(1)
	
#==========================================================================================#
# >>>>> ОБРАБОТКА СПЕЦИАЛЬНЫХ ФЛАГОВ <<<<< #
#==========================================================================================#

# Активна ли опция выключения компьютера по завершении работы парсера.
IsShutdowAfterEnd = False
# Сообщение для внутренних функций: выключение ПК.
InFuncMessage_Shutdown = ""
# Активен ли режим перезаписи при парсинге.
IsForceModeActivated = False
# Сообщение для внутренних функций: режим перезаписи.
InFuncMessage_ForceMode = ""

# Обработка флага: режим перезаписи.
if "f" in CommandDataStruct.flags and CommandDataStruct.name not in ["repair"]:
	# Включение режима перезаписи.
	IsForceModeActivated = True
	# Запись в лог сообщения: включён режим перезаписи.
	logging.info("Force mode: ON.")
	# Установка сообщения для внутренних функций.
	InFuncMessage_ForceMode = "Force mode: ON\n"

else:
	# Запись в лог сообщения об отключённом режиме перезаписи.
	logging.info("Force mode: OFF.")
	# Установка сообщения для внутренних функций.
	InFuncMessage_ForceMode = "Force mode: OFF\n"

# Обработка флага: выключение ПК после завершения работы скрипта.
if "s" in CommandDataStruct.flags:
	# Включение режима.
	IsShutdowAfterEnd = True
	# Запись в лог сообщения о том, что ПК будет выключен после завершения работы.
	logging.info("Computer will be turned off after the script is finished!")
	# Установка сообщения для внутренних функций.
	InFuncMessage_Shutdown = "Computer will be turned off after the script is finished!\n"

#==========================================================================================#
# >>>>> ИНИЦИАЛИЗАЦИЯ МЕНЕДЖЕРА ЗАПРОСОВ <<<<< #
#==========================================================================================#

# Конфигурация менеджера запросов.
Config = WebConfig()
Config.generate_user_agent("pc")
# Инициавлизация менеджера запросов..
Requestor = WebRequestor(Config)
# Установка прокси.
if Settings["proxy"]["enable"] == True: Requestor.add_proxy(
	Protocols.HTTPS,
	host = Settings["proxy"]["host"],
	port = Settings["proxy"]["port"],
	login = Settings["proxy"]["login"],
	password = Settings["proxy"]["password"]
)

#==========================================================================================#
# >>>>> ОБРАБОТКА КОММАНД <<<<< #
#==========================================================================================#

# Обработка команды: collect.
if "collect" == CommandDataStruct.name:
	# Запись в лог сообщения: сбор списка новелл.
	logging.info("====== Collecting ======")
	# Инициализация сборщика.
	CollectorObject = Collector(Settings, Requestor)
	# Фильтры.
	Filters = CommandDataStruct.values["filters"] if "filters" in CommandDataStruct.keys else None
	# Сбор списка алиасов новелл, подходящих под фильтр.
	CollectorObject.collect(Filters, IsForceModeActivated)

# Обработка команды: getcov.
if "getcov" == CommandDataStruct.name:
	# Запись в лог сообщения: заголовок парсинга.
	logging.info("====== Parsing ======")
	# Генерация сообщения.
	ExternalMessage = InFuncMessage_Shutdown + InFuncMessage_ForceMode
	# Парсинг новеллы (без глав).
	LocalNovel = Parser(Settings, Requestor, CommandDataStruct.arguments[0], force_mode = IsForceModeActivated, amend = False, message = ExternalMessage)
	# Сохранение обложки новеллы.
	LocalNovel.download_covers()

# Обработка команд: parse и update.
if CommandDataStruct.name in ["parse", "update"]:
	# Список новелл для парсинга.
	NovelsList = list()
	# Индекс стартового алиаса.
	StartSlugIndex = 0
	# Состояние: выполняется ли обновление.
	IsUpdating = False

	# Если выполняется обновление.
	if CommandDataStruct.name == "update":
		# Запись в лог сообщения: получение списка обновлений.
		logging.info("====== Updating ======")
		# Инициализация сборщика.
		CollectorObject = Collector(Settings, Requestor)
		# Диапазон обновлений.
		Hours = CommandDataStruct.values["hours"] if "hours" in CommandDataStruct.keys else 24
		# Получение списка обновлённых новелл.
		NovelsList = CollectorObject.get_updates(Hours)
		# Переключение состояния обновления.
		IsUpdating = True

	# Запись в лог сообщения: заголовок парсинга.
	logging.info("====== Parsing ======")
	
	# Если активирован флаг парсинга коллекций.
	if not IsUpdating and "collection" in CommandDataStruct.flags:
		
		# Если существует файл коллекции.
		if os.path.exists("Collection.txt"):
			
			# Чтение содржимого файла.
			with open("Collection.txt", "r") as FileReader:
				# Буфер чтения.
				Bufer = FileReader.read().split("\n")
				
				# Для каждой строки.
				for String in Bufer:
					# Если строка не пуста, поместить её в список алиасов.
					if String.strip() != "": NovelsList.append(String.strip())

			# Запись в лог сообщения: количество новелл в коллекции.
			logging.info("Novels count in collection: " + str(len(NovelsList)) + ".")
				
		else:
			# Запись в лог критической ошибки: отсутствует файл коллекций.
			logging.critical("Unable to find collection file.")
			# Выброс исключения.
			raise FileNotFoundError("Collection.txt")
		
	# Если активирован флаг обновления локальных файлов.
	elif not IsUpdating and "local" in CommandDataStruct.flags:
		# Вывод в консоль: идёт поиск новелл.
		print("Scanning novels...")
		# Получение списка файлов в директории.
		NovelsSlugs = os.listdir(Settings["novels-directory"])
		# Фильтрация только файлов формата JSON.
		NovelsSlugs = list(filter(lambda x: x.endswith(".json"), NovelsSlugs))
			
		# Чтение всех алиасов из локальных файлов.
		for File in NovelsSlugs:
			# JSON файл новеллы.
			LocalNovel = ReadJSON(Settings["novels-directory"] + f"/{File}")
			# Помещение алиаса в список.
			NovelsList.append(str(LocalNovel["slug"]) if "slug" in LocalNovel.keys() else str(LocalNovel["dir"]))

		# Запись в лог сообщения: количество доступных для парсинга тайтлов.
		logging.info("Local titles to parsing: " + str(len(NovelsList)) + ".")

	# Если не идёт получение обновлений.
	elif not IsUpdating:
		# Добавление аргумента в очередь парсинга.
		NovelsList.append(CommandDataStruct.arguments[0])

	# Если указан алиас, с которого необходимо начать.
	if "from" in CommandDataStruct.keys:
		
		# Если алиас присутствует в списке.
		if CommandDataStruct.values["from"] in NovelsList:
			# Запись в лог сообщения: парсинг коллекции начнётся с алиаса.
			logging.info("Parcing will be started from \"" + CommandDataStruct.values["from"] + "\".")
			# Задать стартовый индекс, равный индексу алиаса в коллекции.
			StartSlugIndex = NovelsList.index(CommandDataStruct.values["from"])
			
		else:
			# Запись в лог предупреждения: стартовый алиас не найден.
			logging.warning("Unable to find start slug in collection. All titles skipped.")
			# Задать стартовый индекс, равный количеству алиасов.
			StartSlugIndex = len(NovelsList)
			
	# Спарсить каждый тайтл из списка.
	for Index in range(StartSlugIndex, len(NovelsList)):
		# Часть сообщения о прогрессе.
		InFuncMessage_Progress = "Parcing titles: " + str(Index + 1) + " / " + str(len(NovelsList)) + "\n"
		# Генерация сообщения.
		ExternalMessage = InFuncMessage_Shutdown + InFuncMessage_ForceMode + InFuncMessage_Progress if len(NovelsList) > 1 else InFuncMessage_Shutdown + InFuncMessage_ForceMode
		# Парсинг тайтла.
		LocalNovel = Parser(Settings, Requestor, NovelsList[Index], force_mode = IsForceModeActivated, message = ExternalMessage)
		# Загрузка обложек тайтла.
		LocalNovel.download_covers() 
		# Сохранение локальных файлов тайтла.
		LocalNovel.save()
		# Выжидание интервала.
		time.sleep(Settings["delay"])

# Обработка команды: repair.
if "repair" == CommandDataStruct.name:
	# Запись в лог сообщения: восстановление.
	logging.info("====== Repairing ======")
	# Название файла новеллы с расширением.
	Filename = (CommandDataStruct.arguments[0] + ".json") if ".json" not in CommandDataStruct.arguments[0] else CommandDataStruct.arguments[0]
	# Чтение новеллы.
	TitleContent = ReadJSON(Settings["novels-directory"] + f"/{Filename}")
	# Генерация сообщения.
	ExternalMessage = InFuncMessage_Shutdown
	# Вывод в консоль: идёт процесс восстановления главы.
	print("Repairing chapter...")
	# Алиас новеллы.
	NovelSlug = TitleContent["slug"]
	# Парсинг тайтла.
	LocalNovel = Parser(Settings, Requestor, NovelSlug, force_mode = False, amend = False, message = ExternalMessage)
	# Восстановление главы.
	LocalNovel.repair_chapter(CommandDataStruct.values["chapter"])
	# Сохранение локальных файлов новеллы.
	LocalNovel.save(Filename.replace(".json", ""))

#==========================================================================================#
# >>>>> ЗАВЕРШЕНИЕ РАБОТЫ СКРИПТА <<<<< #
#==========================================================================================#

# Закрытие запросчика.
Requestor.close()
# Запись в лог сообщения: заголовок завершения работы скрипта.
logging.info("====== Exiting ======")
# Очистка консоли.
Cls()
# Время завершения работы скрипта.
EndTime = time.time()
# Запись времени завершения работы скрипта.
logging.info("Script finished. Execution time: " + SecondsToTimeString(EndTime - StartTime) + ".")

# Выключение ПК, если установлен соответствующий флаг.
if IsShutdowAfterEnd == True:
	# Запись в лог сообщения о немедленном выключении ПК.
	logging.info("Turning off the computer.")
	# Выключение ПК.
	Shutdown()

# Выключение логгирования.
logging.shutdown()