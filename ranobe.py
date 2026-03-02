from Source.Core.Base.Formats.Ranobe.Elements import Blockquote, Footnote, Header, Image, Paragraph
from Source.Core.Base.Formats.Ranobe.ChapterHeaderParser import ChapterHeaderParser
from Source.Core.Base.Formats.BaseFormat import Cover, Statuses
from Source.Core.Base.Parsers.RanobeParser import RanobeParser
from Source.Core.Base.Formats.Ranobe import Branch, Chapter

from dublib.Polyglot import HTML

from dataclasses import dataclass
import re

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

	def __FindFilledChapter(self, chapters: tuple[Chapter], slug: str) -> Chapter | None:
		"""
		Находит в последовательности первую главу с указанным алиасом и имеющую контент.

		:param chapters: Последовательность глав.
		:type chapters: tuple[Chapter]
		:param slug: Алиас главы.
		:type slug: str
		:return: Данные главы или `None` при отсутствии подходящей.
		:rtype: Chapter | None
		"""

		for CurrentChapter in chapters:
			if CurrentChapter.slug == slug: return CurrentChapter

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

	def __SplitParagraphsByBreaks(self, soup: BeautifulSoup, paragraph: Tag) -> tuple[Tag]:
		"""
		Разбивает абзацы по вхождению тега `br`.

		:param paragraph: Разбиваемый абзац.
		:type paragraph: Tag
		:param soup: Парсер страницы.
		:type soup: BeautifulSoup
		:return: Последовательность абзацев.
		:rtype: tuple[Tag]
		"""

		if not paragraph.find("br"): return (paragraph,)

		Text = paragraph.decode_contents()
		Parts = tuple(Line.strip() for Line in re.split(r"<br\s*/?>", Text) if Line.strip())

		return tuple(soup.new_tag("p", string = Part, attrs = paragraph.attrs.copy()) for Part in Parts)

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

	def __GetCovers(self, data: dict):
		"""
		Получает ссылки на обложки.

		:param data: Словарь данных тайтла.
		:type data: dict
		"""

		Posters: dict[str, str] = data["posters"]
		del Posters["color"]
		Covers = list()

		for Link in Posters.values():

			if Link.endswith("default.jpg"):
				self._Portals.covers_unstubbed()
				Covers = list()
				break

			Covers.append(Cover(self._SystemObjects, self).set_link(Link))

		self._Title.set_covers(Covers)

	def __GetDescription(self, data: dict):
		"""
		Получает описание тайтла.

		:param data: Словарь данных тайтла.
		:type data: dict
		"""

		DescriptionParagraphs = BeautifulSoup(data["description"], "html.parser").find_all("p")
		Description: list[str] = list()

		for Paragraph in DescriptionParagraphs:
			Paragraph = Paragraph.decode_contents()
			Paragraph = HTML(Paragraph).plain_text.strip()
			Description.append(Paragraph)

		self._Title.set_description("\n".join(Description))

	def __GetNames(self, soup: BeautifulSoup, data: dict):
		"""
		Парсит названия тайтла.

		:param soup: Парсер HTML-секции данных тайтла.
		:type soup: BeautifulSoup
		:param data: Словарь данных тайтла.
		:type data: dict
		"""

		self._Title.set_localized_name(data["names"]["rus"])
		self._Title.set_eng_name(data["names"]["eng"])
		
		AnotherNames = soup.find("a", {"class": "ui header tiny grey"})

		if AnotherNames:
			AnotherNames = AnotherNames.get_text().split(" / ")
			AnotherNames = tuple(Name.strip() for Name in AnotherNames)
			self._Title.set_another_names(AnotherNames)

	def __GetOriginalLanguage(self, soup: BeautifulSoup):
		"""
		Определяет код языка оригинального контента по стандарту ISO 639-1.

		:param soup: Парсер HTML-секции данных тайтла.
		:type soup: BeautifulSoup
		"""

		LanguagesDeterminations = {
			"china": "zho",
			"kr": "kor",
			"japan": "jpn",
			"us": "eng"
		}

		Flag = soup.find("i")

		if Flag:
			CountryCode = Flag.attrs["class"][0]
			self._Title.set_original_language(LanguagesDeterminations[CountryCode])

	def __GetStatus(self, data: dict):
		"""
		Определяет статус тайтла.

		:param data: Словарь данных тайтла.
		:type data: dict
		"""

		StatusesDeterminations = {
			"В процессе": Statuses.ongoing,
			"Заморожено": Statuses.dropped,
			"Завершено": Statuses.completed
		}

		self._Title.set_status(StatusesDeterminations[data["status"]["title"]])

	def __GetTagsAngAgeLimit(self, data: dict):
		"""
		Получает теги тайтла и определяет возрастной рейтинг.

		:param data: Словарь данных тайтла.
		:type data: dict
		"""

		Tags = list()
		for Tag in data["tags"]["events"]: Tags.append(Tag["title"])
		
		Ratings = {
			"18+": 18,
			"R-15 (Японское возрастное ограничение)": 15
		}

		for Rating, AgeLimit in Ratings.items():
			if Rating in Tags:
				if self._Settings.common.pretty: Tags.remove(Rating)
				self._Title.set_age_limit(AgeLimit)
				break

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

				case "p":
					for CurrentParagraph in self.__SplitParagraphsByBreaks(Soup, CurrentTag):
						Element = self.__CreateParagraphElementFromTag(CurrentParagraph, FootnotesDict)

						if Element:
							chapter.add_element(Element)
							Element = None

				case "h3": Element = self.__CreateHeaderElementFromTag(CurrentTag, FootnotesDict)
				case "img": Element = self.__CreateImageElementFromTag(CurrentTag, chapter)
				case "blockquote": Element = self.__CreateBlockquoteElementFromTag(CurrentTag, chapter, FootnotesDict)

			if Element: chapter.add_element(Element)

	def parse(self):
		"""Получает основные данные тайтла."""

		self._Title.set_id(int(self._Title.slug.split("-")[0]))
		self._Title.set_content_language("rus")

		Response = self._Requestor.get(f"https://ranobehub.org/api/ranobe/{self._Title.id}")
		if not Response.ok: self._Portals.request_error(Response, "Unable request title data.")
		Data = Response.json["data"]
		Soup = BeautifulSoup(Data["html"], "html.parser")

		self.__GetNames(Soup, Data)
		self.__GetCovers(Data)
		for AuthorData in Data["authors"]: self._Title.add_author(AuthorData["name_eng"])
		self._Title.set_publication_year(Data["year"])
		self.__GetDescription(Data)
		self.__GetOriginalLanguage(Soup)
		self.__GetStatus(Data)
		for Genre in Data["tags"]["genres"]: self._Title.add_genre(Genre["title"])
		self.__GetTagsAngAgeLimit(Data)
		self.__GetBranch()

	def postprocessor(self):
		"""Вносит изменения в тайтл непосредственно перед сохранением."""

		EmptyChaptersRemoved = 0

		for CurrentBranch in self._Title.branches:
			for CurrentChapter in CurrentBranch.chapters:
				if not CurrentChapter.paragraphs:
					Slug = CurrentChapter.slug
					FilledChapter = self.__FindFilledChapter(CurrentBranch.chapters, Slug)

					if FilledChapter:
						CurrentBranch.remove_chapter(CurrentChapter.id)
						EmptyChaptersRemoved += 1

		if EmptyChaptersRemoved: self._Portals.info(f"Redirecting chapters removed: {EmptyChaptersRemoved}.")