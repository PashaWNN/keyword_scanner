import unittest
import my_core

class CoreTests(unittest.TestCase):

  def test_parse_sitemap(self):
    link = 'http://gryadka77.ru/sitemap.728436.xml'
    self.assertEqual(my_core.parse_sitemap(link)[:3], 
                    ['http://gryadka77.ru/bortiki-dlya-sborki', 
                     'http://gryadka77.ru/parniki-1', 
                     'http://gryadka77.ru/setka-ot-krotov'])

  


if __name__=='__main__':
  unittest.main()
