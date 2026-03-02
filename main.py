from Source.Core.Base.SourceOperator import BaseSourceOperator

from datetime import datetime
from time import sleep

class SourceOperator(BaseSourceOperator):
	"""Оператор источника."""

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ КОЛЛЕКЦИОНИРОВАНИЯ <<<<< #
	#==========================================================================================#

	def __Collect(self, filters: str | None = None, pages: int | None = None) -> tuple[str]:
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

	def __CollectUpdates(self, period: int, pages: int | None = None) -> tuple[str]:
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
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

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

		Slugs = self.__Collect(filters, pages) if not period else self.__CollectUpdates(period, pages)

		return Slugs