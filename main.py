from Source.Core.Base.Formats.Ranobe import Branch, Chapter, ChapterHeaderParser
from Source.Core.Base.Parsers.RanobeParser import RanobeParser
from Source.Core.Base.Formats.BaseFormat import Statuses

from dublib.Methods.Data import RemoveRecurringSubstrings
from dublib.Polyglot import HTML

from time import sleep
import datetime

from bs4 import BeautifulSoup, Tag
import dateparser

class Parser(RanobeParser):
	"""Парсер."""

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __GetDataBlockContent(self, soup: BeautifulSoup, header: str) -> str | None:
		"""
		Получает содержимое блока данных.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		:param header: Ключевая строка для идентификации блока.
		:type header: str
		:return: Содержимое искомого блока данных.
		:rtype: str | None
		"""

		DataContainer = soup.find("div", {"id": "section-common"})

		if not DataContainer:
			self._Portals.warning(f"Data container not found.")
			return
		
		DataBlocks = DataContainer.find_all("div", {"class": "book-meta-row"})

		if not DataBlocks:
			self._Portals.warning(f"No data block for header: \"{header}\".")
			return
		
		for Block in DataBlocks:
			if header in str(Block): return Block.get_text().strip()[len(header):].strip()

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ ПАРСИНГА СТРАНИЦЫ ТАЙТЛА <<<<< #
	#==========================================================================================#

	def __GetAuthor(self, soup: BeautifulSoup):
		"""
		Получает автора.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""
		AuthorContainer = soup.find("div", {"class": "book-author"})

		if AuthorContainer:
			Author = AuthorContainer.get_text().replace("(Автор)", "").strip().split("\n")[0]
			self._Title.add_author(Author)

	def __GetCovers(self, soup: BeautifulSoup):
		"""
		Получает ссылки на обложки.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		CoversBlocks = soup.find("div", {"class": "sticky"}).find("div", {"class": "poster-slider"}).find_all("img")
		
		for Block in CoversBlocks:
			Link = Block["data-src"]
			# Исключает заглушку.
			if not Link.endswith("default.jpg"): self._Title.add_cover(Link)

	def __GetDescription(self, soup: BeautifulSoup):
		"""
		Получает описание тайтла.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		DescriptionBlock = soup.find("div", {"class": "book-description"})
		Description = None
		
		if DescriptionBlock:
			Paragraphs = DescriptionBlock.find_all("p")
			Description = ""
			for p in Paragraphs: Description += HTML(p.get_text()).plain_text.strip() + "\n"
				
		Description = RemoveRecurringSubstrings(Description, "\n")
		Description = Description.strip("\n")
		self._Title.set_description(Description)

	def __GetGenres(self, soup: BeautifulSoup):
		"""
		Получает жанры тайтла.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		Genres = self.__GetDataBlockContent(soup, "Жанр")

		if Genres:
			Genres = Genres.split()
			Genres = tuple(Genre for Genre in Genres if Genre)
			self._Title.set_genres(Genres)

	def __GetNames(self, soup: BeautifulSoup):
		"""
		Парсит названия тайтла.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		self._Title.set_localized_name(soup.find("h1").get_text())
		AnotherNames = soup.find("h2").get_text().split(" / ")
		self._Title.set_eng_name(AnotherNames[0])
		if len(AnotherNames) > 1: self._Title.set_another_names(AnotherNames[1:])

	def __GetOriginalLanguage(self, soup: BeautifulSoup):
		"""
		Определяет код языка оригинального контента по стандарту ISO 639-1.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		LanguagesDeterminations = {
			"Китай": "zho",
			"Корея": "kor",
			"Япония": "jpn",
			"США": "eng"
		}
		
		Country = self.__GetDataBlockContent(soup, "Страна")
		if Country in LanguagesDeterminations: self._Title.set_original_language(LanguagesDeterminations[Country])

	def __GetPublicationYear(self, soup: BeautifulSoup):
		"""
		Получает год публикации тайтла.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		Year = self.__GetDataBlockContent(soup, "Год выпуска")
		if not Year: return
		if Year.isdigit(): self._Title.set_publication_year(int(Year))
		else: self._Portals.warning("Failed to get publication year.")

	def __GetStatus(self, soup: BeautifulSoup):
		"""
		Определяет статус тайтла.

		:param soup: _description_
		:type soup: BeautifulSoup
		"""

		StatusesDeterminations = {
			"В процессе": Statuses.ongoing,
			"Заморожено": Statuses.dropped,
			"Завершено": Statuses.completed
		}

		Status = self.__GetDataBlockContent(soup, "Статус перевода")
		if Status in StatusesDeterminations: self._Title.set_status(StatusesDeterminations[Status])

	def __GetTagsAngAgeLimit(self, soup: BeautifulSoup):
		"""
		Получает теги тайтла и определяет возрастной рейтинг.

		:param soup: Страница тайтла.
		:type soup: BeautifulSoup
		"""

		Tags = list()

		DataContainer = soup.find_all("div", {"class": "book-tags"})[-1]
		DataSpoiler = DataContainer.find("div", {"class": "__spoiler_new display-none"})
		DataBlocks = DataSpoiler.find_all("a") if DataSpoiler else DataContainer.find_all("a")
		for Block in DataBlocks: Tags.append(Block.get_text().strip())
		
		Ratings = {
			"R-15 (Японское возрастное ограничение)": 15,
			"18+": 18
		}

		for Rating, AgeLimit in Ratings.items():
			if Rating in Tags:
				if self._Settings.common.pretty: Tags.remove(Rating)
				self._Title.set_age_limit(AgeLimit)

		self._Title.set_tags(Tags)

	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def amend(self, branch: Branch, chapter: Chapter):
		"""
		Дополняет главу дайными о слайдах.

		:param branch: Данные ветви.
		:type branch: Branch
		:param chapter: Данные главы.
		:type chapter: Chapter
		"""

		pass

	def parse(self):
		"""Получает основные данные тайтла."""

		Response = self._Requestor.get(f"https://{self._Manifest.site}/ranobe/{self._Title.slug}")
		if not Response.ok: self._Portals.request_error(Response, "Unable load title page.")

		self._Title.set_id(int(self._Title.slug.split("-")[0]))
		self._Title.set_content_language("rus")

		Soup = BeautifulSoup(Response.text, "html.parser")
		self.__GetNames(Soup)
		self.__GetCovers(Soup)
		self.__GetAuthor(Soup)
		self.__GetPublicationYear(Soup)
		self.__GetDescription(Soup)
		self.__GetOriginalLanguage(Soup)
		self.__GetStatus(Soup)
		self.__GetGenres(Soup)
		self.__GetTagsAngAgeLimit(Soup)