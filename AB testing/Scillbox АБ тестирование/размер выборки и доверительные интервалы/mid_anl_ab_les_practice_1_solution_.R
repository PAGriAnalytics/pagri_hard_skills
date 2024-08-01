### Practice ###

# 1

install.packages("DescTools")
library(DescTools)

# 2

BinomCI(60, 100, conf.level = 0.95)

# 4
BinomCI(80, 100, conf.level = 0.95)

# in addition

ages <- c(23, 24, 34, 33, 38)
MeanCI(ages)
