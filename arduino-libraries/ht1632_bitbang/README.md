# ht1632_bitbang

While testing, some HT1632C chips from eBay completely glitched out with some existing HT1632C libraries. I suspect this is due to counterfeit chips, which are rather common on eBay, not being able to handle something they do.

This library is a quick and dirty replacement that seems to work with the chips I bought, written using only the HT1632C datasheet as reference.

The goal is to re-test the existing libraries with our chips, re-test both libraries with chips from a reputable source, and use the existing libraries if we find a reliable configuration, but in the meanwhile, this is what we build with.

