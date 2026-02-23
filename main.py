from Source.Core.Base.Formats.Ranobe.Elements import Blockquote, Footnote, Header, Image, Paragraph
from Source.Core.Base.Formats.Ranobe.ChapterHeaderParser import ChapterHeaderParser
from Source.Core.Base.Parsers.RanobeParser import RanobeParser
from Source.Core.Base.Formats.Ranobe import Branch, Chapter
from Source.Core.Base.Formats.BaseFormat import Statuses

from dublib.Methods.Data import RemoveRecurringSubstrings
from dublib.Polyglot import HTML

from dataclasses import dataclass
from datetime import datetime
from time import sleep

from bs4 import BeautifulSoup, Tag

@dataclass(frozen = True)
class FootnotesSearchResult:
	text: str
	footnotes: list[Footnote]

class Parser(RanobeParser):
	"""Парсер."""

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __FindFootnotesByAnchors(self, tag: Tag, text: str, footnotes_dict: dict[str, Footnote]) -> FootnotesSearchResult:
		"""
		Ищет ссылки на заметки и на их основе создаёт объекты `Footnote`.

		:param tag: Обрабатываемый тег.
		:type tag: Tag
		:param text: Текст элемента.
		:type text: str
		:param footnotes_dict: Словарь из контента заметок главы, полученный при помощи метода `__GetFootnotes()`.
		:type footnotes_dict: dict[str, Footnote]
		:return: _description_
		:rtype: list[Footnote]
		"""

		Footnotes = list()

		for Anchor in tag.find_all("a"):

			Href = Anchor.get("href")
			if not Href or not Href.startswith("#"):
				Anchor.decompose()
				continue
			
			FootnoteID = Href[1:]
			FootnoteObject = footnotes_dict[FootnoteID]
			FootnoteObject.set_placeholder(Anchor.get_text().strip())
			text = FootnoteObject.replace_in_text(text, str(Anchor))
			Footnotes.append(FootnoteObject)

		return FootnotesSearchResult(text, Footnotes)

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

	def __UnwrapInnerTags(self, tag: Tag) -> Tag:
		"""
		Если передан тег абзаца, содержащий блок текста или изображение, разворачивает абзац.

		:param tag: Обрабатываемый тег.
		:type tag: Tag
		:return: Обрабатываемый тег или вложенный тег блока текста или изображения.
		:rtype: Tag
		"""

		if tag.name == "p":
			for InnerTagName in ("blockquote", "img", "h3"):
				InnerTag = tag.find(InnerTagName)
				if InnerTag:
					tag = InnerTag
					break

		return tag

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ КОЛЛЕКЦИОНИРОВАНИЯ <<<<< #
	#==========================================================================================#

	def _Collect(self, filters: str | None = None, pages: int | None = None) -> tuple[str]:
		"""
		Собирает список тайтлов по заданным параметрам.

		:param filters: Строка из URI каталога, описывающая параметры запроса.
		:type filters: str | None
		:param pages: Количество запрашиваемых страниц.
		:type pages: int | None
		:raises ParsingError: Выбрасывается при ошибке коллекционирования.
		:return: Набор алиасов собранных тайтлов.
		:rtype: tuple[str]
		"""

		Slugs = list()
		Page = 1

		if filters: filters = "&" + filters.strip("&")
		else: filters = ""
		
		while True:
			PageQuery = f"&page={Page}" if Page != 1 else ""
			Response = self._Requestor.get(f"https://{self._Manifest.site}/api/search?{filters}{PageQuery}".lstrip("?"))
			if not Response.ok: self._Portals.request_error(Response, "Unable to request catalog.")

			CatalogNotes = Response.json["resource"]
			if not CatalogNotes: break

			for Note in CatalogNotes: Slugs.append(Note["url"].split("/ranobe/")[-1])

			if Page == pages: break
			self._Portals.collect_progress_by_page(Page)
			Page += 1
			sleep(self._Settings.common.delay)

		return tuple(Slugs)

	def _CollectUpdates(self, period: int, pages: int | None = None) -> tuple[str]:
		"""
		Собирает алиасы тайтлов, обновлённых за указанный период времени (в часах).

		:param period: Количество часов до текущего момента, составляющее период получения данных.
		:type period: int
		:param pages: Количество запрашиваемых страниц.
		:type pages: int | None
		:return: Последовательность алиасов тайтлов.
		:rtype: tuple[str]
		:raises ParsingError: Выбрасывается при ошибке получения обновлений.
		"""

		Slugs = list()
		Page = 1
		Now = datetime.now()
		period = period * 3600
		IsCollected = False
		
		while not IsCollected:
			# Первая страница не должна иметь параметра page.
			PageQuery = f"&page={Page}" if Page != 1 else ""
			Response = self._Requestor.get(f"https://{self._Manifest.site}/api/feed?take=40{PageQuery}")
			if not Response.ok: self._Portals.request_error(Response, "Unable to request updates.")

			for Note in Response.json["resource"]:
				for NoteElement in Note["items"]:
					Slug = NoteElement["ranobe"]["url"].split("/ranobe/")[-1]
					LastUpdate = NoteElement["updates"][0]
					UpdateDate = datetime.fromtimestamp(LastUpdate["created_at"])
					Delta = Now - UpdateDate

					if Delta.total_seconds() <= period: Slugs.append(Slug)
					else: IsCollected = True

			self._Portals.collect_progress_by_page(Page)
			Page += 1
			if pages and Page > pages: IsCollected = True
			sleep(self._Settings.common.delay)

		return tuple(Slugs)

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ СОЗДАНИЯ ЭЛЕМЕНТОВ ГЛАВ <<<<< #
	#==========================================================================================#

	def __CreateBlockquoteElementFromTag(self, tag: Tag, chapter: Chapter, footnotes_dict: dict[str, Footnote]) -> Blockquote:
		"""
		Создаёт элемент `Blockquote` из тега блока текста.

		:param tag: Тег блока текста.
		:type tag: Tag
		:param chapter: Данные главы.
		:type chapter: Chapter
		:param footnotes_dict: Словарь из контента заметок главы, полученный при помощи метода `__GetFootnotes()`.
		:type footnotes_dict: dict[str, Footnote]
		:return: Элемент страницы.
		:rtype:Blockquotee
		"""

		BlockquoteObject = Blockquote()

		for CurrentTag in tag.find_all(("p", "img"), recursive = False):
			Element = None

			match CurrentTag.name:
				case "p": Element = self.__CreateParagraphElementFromTag(CurrentTag, footnotes_dict)
				case "img": Element = self.__CreateImageElementFromTag(CurrentTag, chapter)

			BlockquoteObject.add_element(Element)
		
		return BlockquoteObject

	def __CreateHeaderElementFromTag(self, tag: Tag, footnotes_dict: dict[str, Footnote]) -> Header | None:
		"""
		Создаёт элемент `Header` из тега заголовка.

		:param tag: Тег заголовка.
		:type tag: Tag
		:param footnotes_dict: Словарь из контента заметок главы, полученный при помощи метода `__GetFootnotes()`.
		:type footnotes_dict: dict[str, Footnote]
		:return: Элемент страницы или `None` в случае игнорирования абзаца.
		:rtype: Image
		"""

		HeaderObject = Header(self._SystemObjects)
		Text = tag.decode_contents().strip()
		Footnotes = list()
		if not Text: return

		SearchResult = self.__FindFootnotesByAnchors(tag, Text, footnotes_dict)
		Text = SearchResult.text
		Footnotes += SearchResult.footnotes

		HeaderObject.set_text(Text)
		for Note in Footnotes: HeaderObject.add_footnote(Note)
		HeaderObject.parse_align(tag)
		
		return HeaderObject

	def __CreateImageElementFromTag(self, tag: Tag, chapter: Chapter) -> Image:
		"""
		Создаёт элемент `Image` из тега изображения.

		:param tag: Тег изображения.
		:type tag: Tag
		:param chapter: Данные главы.
		:type chapter: Chapter
		:return: Элемент страницы.
		:rtype: Image
		"""

		tag.attrs["src"] = f"https://{self._Manifest.site}/api/media/" + tag.attrs["data-media-id"]
		ImageObject = Image(self._SystemObjects, self, chapter)
		ImageObject.parse_image(tag)
		
		return ImageObject
	
	def __CreateParagraphElementFromTag(self, tag: Tag, footnotes_dict: dict[str, Footnote]) -> Paragraph | None:
		"""
		Создаёт элемент `Paragraph` из тега абзаца.

		:param tag: Тег абзаца.
		:type tag: Tag
		:param footnotes_dict: Словарь из контента заметок главы, полученный при помощи метода `__GetFootnotes()`.
		:type footnotes_dict: dict[str, Footnote]
		:return: Элемент страницы или `None` в случае игнорирования абзаца.
		:rtype: Image
		"""

		ParagraphObject = Paragraph(self._SystemObjects)
		for Break in tag.find_all("br"): Break.decompose()
		Text = tag.decode_contents().strip()
		Footnotes = list()
		if not Text: return

		SearchResult = self.__FindFootnotesByAnchors(tag, Text, footnotes_dict)
		Text = SearchResult.text
		Footnotes += SearchResult.footnotes
		
		ParagraphObject.set_text(Text)
		for Note in Footnotes: ParagraphObject.add_footnote(Note)
		ParagraphObject.parse_align(tag)
		
		return ParagraphObject

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

	def __GetBranch(self):
		"""Получает данные глав."""

		Response = self._Requestor.get(f"https://{self._Manifest.site}/api/ranobe/{self._Title.id}/contents")
		if not Response.ok: self._Portals.request_error(Response, "Unable to get branch data.")

		CurrentBranch = Branch(self._Title.id)

		for Volume in Response.json["volumes"]:

			for ChapterData in Volume["chapters"]:
				CurrentChapter = Chapter(self._SystemObjects, self._Title)
				HeaderData = ChapterHeaderParser(ChapterData["name"], self._Title).parse()

				CurrentChapter.set_volume(Volume["num"])
				CurrentChapter.set_id(ChapterData["id"])
				CurrentChapter.set_name(HeaderData.name)
				CurrentChapter.set_number(HeaderData.number)
				CurrentChapter.set_type(HeaderData.type)
				CurrentChapter.set_slug(ChapterData["url"].split("ranobe/")[-1])
				CurrentBranch.add_chapter(CurrentChapter)

		self._Title.add_branch(CurrentBranch)

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

	def __GetFootnotes(self, container: Tag) -> dict[str, Footnote]:
		"""
		Возвращает словарь заметок.

		:param container: Контейнер контента главы.
		:type container: Tag
		:return: Словарь, в котором ключ – ID заметки на сайте, а значение – сама заметка.
		:rtype: dict[str, Footnote]
		"""

		FootnotesDict = dict()
		ReferencesList: list[Tag] = list()

		#---> В некоторых главах несколько списков сновок.
		#==========================================================================================#
		References = container.find_all("ol")
		if not References: return FootnotesDict

		for Reference in References:
			Buffer = Reference.find_all("li")

			if Buffer: 
				for CurrentBufferElement in Buffer: ReferencesList.append(CurrentBufferElement)

		#---> Получение содержимого заметки для каждого элемента списка.
		#==========================================================================================#
		for Reference in ReferencesList:
			ReferenceID = Reference.attrs.get("id")
			if not ReferenceID: self._Portals.warning("Reference hasn't ID. Skipped.")
			Reference.find("a").decompose()

			ParagraphObject = Paragraph(self._SystemObjects)
			ParagraphObject.set_text(Reference.get_text())
			FootnoteObject = Footnote(self._SystemObjects)
			FootnoteObject.add_element(ParagraphObject)
			FootnotesDict[ReferenceID] = FootnoteObject

		return FootnotesDict

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
		
		Response = self._Requestor.get(f"https://{self._Manifest.site}/ranobe/{chapter.slug}")
		if not Response.ok: self._Portals.request_error(Response, "Unable load chapter page.")
		
		Soup = BeautifulSoup(Response.text, "lxml")
		Container: Tag = Soup.find("div", {"data-container": str(chapter.id)})

		if not Container:
			self._Portals.chapter_not_found(chapter)
			return

		# Удаление элементов интерфейса.
		for Trash in Container.find_all("div"): Trash.decompose()

		FootnotesDict = self.__GetFootnotes(Container)
		for CurrentTag in Container.find_all(("p", "h3", "img", "blockquote"), recursive = False):
			CurrentTag = self.__UnwrapInnerTags(CurrentTag)
			Element = None

			match CurrentTag.name:
				case "p": Element = self.__CreateParagraphElementFromTag(CurrentTag, FootnotesDict)
				case "h3": Element = self.__CreateHeaderElementFromTag(CurrentTag, FootnotesDict)
				case "img": Element = self.__CreateImageElementFromTag(CurrentTag, chapter)
				case "blockquote": Element = self.__CreateBlockquoteElementFromTag(CurrentTag, chapter, FootnotesDict)

			if Element: chapter.add_element(Element)

	def collect(self, period: int | None = None, filters: str | None = None, pages: int | None = None) -> tuple[str]:
		"""
		Собирает список алиасов тайтлов по заданным параметрам.

		:param period: Количество часов до текущего момента, составляющее период получения данных.
		:type period: int | None
		:param filters: Строка, описывающая фильтрацию (подробнее в README.md парсера).
		:type filters: str | None
		:param pages: Количество запрашиваемых страниц каталога.
		:type pages: int | None
		:return: Набор собранных алиасов.
		:rtype: tuple[str]
		"""

		Slugs = self._Collect(filters, pages) if not period else self._CollectUpdates(period, pages)

		return Slugs

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
		self.__GetBranch()